-- Save-to-Action Engine additions, plus what the settings page needs.

-- "Right now for you": a save brought back because of something coming up.
create table public.recall_cards (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  event_id uuid references public.calendar_events (id) on delete cascade,
  title text not null,
  body text not null,
  save_ids uuid[] not null default '{}',
  expires_at timestamptz not null,
  dismissed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, event_id)
);
create index recall_cards_user_idx on public.recall_cards (user_id, expires_at);
alter table public.recall_cards enable row level security;
create trigger set_updated_at before update on public.recall_cards
  for each row execute function public.set_updated_at();
create policy recall_cards_select on public.recall_cards for select to authenticated
  using (user_id = (select auth.uid()) and public.has_workspace_role(workspace_id, 'viewer'));
-- Only dismissing is allowed from clients; agents create cards with the service role.
create policy recall_cards_update on public.recall_cards for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));
revoke update on public.recall_cards from authenticated;
grant update (dismissed_at) on public.recall_cards to authenticated;

-- How many times a task has been put off, so the follow-up loop can adapt.
alter table public.tasks add column skip_count integer not null default 0;

-- Exam dates and other deadlines count as calendar events.
alter table public.calendar_events add column is_deadline boolean not null default false;

-- Per-user daily AI usage, for the cap shown in Settings. Service role only.
create table public.ai_usage (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  day date not null default current_date,
  count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, day)
);
alter table public.ai_usage enable row level security;
create trigger set_updated_at before update on public.ai_usage
  for each row execute function public.set_updated_at();

-- Team workspaces must be createable by their owner, but personal ones stay unique.
create unique index workspaces_one_personal_per_owner
  on public.workspaces (owner_id) where type = 'personal';
