-- Ingestion: progress tracking on saves, and jobs created atomically with them.

alter table public.saves
  add column stage text,
  add column error text,
  add column language text;

-- Created by trigger, in the save's own transaction. So a save can never exist
-- without its job, and a job can never run before its save is visible. Clients have
-- no direct access to jobs, hence SECURITY DEFINER.
create function public.enqueue_ingestion() returns trigger
language plpgsql security definer
set search_path = ''
as $$
begin
  insert into public.jobs (type, payload)
  values ('ingest_save', jsonb_build_object('save_id', new.id));
  return new;
end;
$$;

create trigger enqueue_ingestion_on_insert
  after insert on public.saves
  for each row when (new.status = 'pending')
  execute function public.enqueue_ingestion();

-- A retry moves a failed save back to pending.
create trigger enqueue_ingestion_on_retry
  after update of status on public.saves
  for each row when (old.status = 'failed' and new.status = 'pending')
  execute function public.enqueue_ingestion();
