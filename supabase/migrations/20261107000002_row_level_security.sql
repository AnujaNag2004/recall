-- Row-level security: the database enforces tenancy even if an API check is missed.
--
-- Access model:
--   viewer  reads workspace content
--   member  also creates and edits content
--   admin   also manages members and invites, and renames the workspace
--   owner   also deletes the workspace
-- The anon role gets nothing. Tables with RLS enabled but no policy are reachable
-- only by the API's service role, which bypasses RLS.

revoke all on all tables in schema public from anon;

-- ---------------------------------------------------------------------------
-- Helpers
--
-- SECURITY DEFINER so that a policy on workspace_members can consult
-- workspace_members without recursing into itself. search_path is pinned empty
-- so a caller cannot redirect any name these functions resolve.
-- ---------------------------------------------------------------------------

create function public.has_workspace_role(
  target_workspace uuid,
  minimum public.workspace_role
) returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.workspace_members m
    where m.workspace_id = target_workspace
      and m.user_id = (select auth.uid())
      and m.role >= minimum
  )
$$;

create function public.has_save_role(
  target_save uuid,
  minimum public.workspace_role
) returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.saves s
    join public.workspace_members m on m.workspace_id = s.workspace_id
    where s.id = target_save
      and m.user_id = (select auth.uid())
      and m.role >= minimum
  )
$$;

create function public.has_task_role(
  target_task uuid,
  minimum public.workspace_role
) returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.tasks t
    join public.workspace_members m on m.workspace_id = t.workspace_id
    where t.id = target_task
      and m.user_id = (select auth.uid())
      and m.role >= minimum
  )
$$;

create function public.has_topic_role(
  target_topic uuid,
  minimum public.workspace_role
) returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.topics t
    join public.workspace_members m on m.workspace_id = t.workspace_id
    where t.id = target_topic
      and m.user_id = (select auth.uid())
      and m.role >= minimum
  )
$$;

create function public.shares_workspace_with(other_user uuid) returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.workspace_members mine
    join public.workspace_members theirs on theirs.workspace_id = mine.workspace_id
    where mine.user_id = (select auth.uid())
      and theirs.user_id = other_user
  )
$$;

revoke execute on function public.has_workspace_role(uuid, public.workspace_role) from anon, public;
revoke execute on function public.has_save_role(uuid, public.workspace_role) from anon, public;
revoke execute on function public.has_task_role(uuid, public.workspace_role) from anon, public;
revoke execute on function public.has_topic_role(uuid, public.workspace_role) from anon, public;
revoke execute on function public.shares_workspace_with(uuid) from anon, public;

-- A workspace's creator always becomes its owner, in the same transaction.
create function public.add_workspace_owner_as_member() returns trigger
language plpgsql security definer
set search_path = ''
as $$
begin
  insert into public.workspace_members (workspace_id, user_id, role)
  values (new.id, new.owner_id, 'owner')
  on conflict (workspace_id, user_id) do update set role = 'owner';
  return new;
end;
$$;

create trigger add_owner_as_member
  after insert on public.workspaces
  for each row execute function public.add_workspace_owner_as_member();

-- ---------------------------------------------------------------------------
-- Enable RLS on every table, so nothing is reachable by default
-- ---------------------------------------------------------------------------

do $$
declare
  table_name text;
begin
  for table_name in
    select c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r'
  loop
    execute format('alter table public.%I enable row level security', table_name);
  end loop;
end;
$$;

-- ---------------------------------------------------------------------------
-- Profiles: visible to yourself and people you share a workspace with
-- ---------------------------------------------------------------------------

create policy profiles_select on public.profiles for select to authenticated
  using (user_id = (select auth.uid()) or public.shares_workspace_with(user_id));
create policy profiles_insert on public.profiles for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy profiles_update on public.profiles for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

-- ---------------------------------------------------------------------------
-- Workspaces
-- ---------------------------------------------------------------------------

create policy workspaces_select on public.workspaces for select to authenticated
  using (owner_id = (select auth.uid()) or public.has_workspace_role(id, 'viewer'));
create policy workspaces_insert on public.workspaces for insert to authenticated
  with check (owner_id = (select auth.uid()));
create policy workspaces_update on public.workspaces for update to authenticated
  using (public.has_workspace_role(id, 'admin'))
  with check (public.has_workspace_role(id, 'admin'));
create policy workspaces_delete on public.workspaces for delete to authenticated
  using (public.has_workspace_role(id, 'owner'));

-- Clients may only rename. Without this an admin could reassign owner_id;
-- ownership transfer belongs to the API, through the service role.
revoke update on public.workspaces from authenticated;
grant update (name) on public.workspaces to authenticated;

-- Admins manage members, but no client can create, change or remove an owner row:
-- that would allow taking over a workspace or locking its owner out.
create policy workspace_members_select on public.workspace_members for select to authenticated
  using (public.has_workspace_role(workspace_id, 'viewer'));
create policy workspace_members_insert on public.workspace_members for insert to authenticated
  with check (public.has_workspace_role(workspace_id, 'admin') and role <> 'owner');
create policy workspace_members_update on public.workspace_members for update to authenticated
  using (public.has_workspace_role(workspace_id, 'admin') and role <> 'owner')
  with check (public.has_workspace_role(workspace_id, 'admin') and role <> 'owner');
-- Anyone but the owner may also leave on their own.
create policy workspace_members_delete on public.workspace_members for delete to authenticated
  using (
    role <> 'owner'
    and (user_id = (select auth.uid()) or public.has_workspace_role(workspace_id, 'admin'))
  );

create policy invites_all on public.invites for all to authenticated
  using (public.has_workspace_role(workspace_id, 'admin'))
  with check (public.has_workspace_role(workspace_id, 'admin') and role <> 'owner');

-- ---------------------------------------------------------------------------
-- Content with a workspace_id: viewers read, members write
-- ---------------------------------------------------------------------------

do $$
declare
  table_name text;
begin
  foreach table_name in array array['saves', 'save_chunks', 'topics', 'tasks', 'flashcards']
  loop
    execute format(
      'create policy %1$s_select on public.%1$I for select to authenticated
         using (public.has_workspace_role(workspace_id, ''viewer''));
       create policy %1$s_insert on public.%1$I for insert to authenticated
         with check (public.has_workspace_role(workspace_id, ''member''));
       create policy %1$s_update on public.%1$I for update to authenticated
         using (public.has_workspace_role(workspace_id, ''member''))
         with check (public.has_workspace_role(workspace_id, ''member''));
       create policy %1$s_delete on public.%1$I for delete to authenticated
         using (public.has_workspace_role(workspace_id, ''member''));',
      table_name
    );
  end loop;
end;
$$;

-- ---------------------------------------------------------------------------
-- Content attached to a save
-- ---------------------------------------------------------------------------

do $$
declare
  table_name text;
begin
  foreach table_name in array array['transcript_segments', 'entities', 'resources']
  loop
    execute format(
      'create policy %1$s_select on public.%1$I for select to authenticated
         using (public.has_save_role(save_id, ''viewer''));
       create policy %1$s_insert on public.%1$I for insert to authenticated
         with check (public.has_save_role(save_id, ''member''));
       create policy %1$s_update on public.%1$I for update to authenticated
         using (public.has_save_role(save_id, ''member''))
         with check (public.has_save_role(save_id, ''member''));
       create policy %1$s_delete on public.%1$I for delete to authenticated
         using (public.has_save_role(save_id, ''member''));',
      table_name
    );
  end loop;
end;
$$;

-- ---------------------------------------------------------------------------
-- Knowledge graph links: both ends must be reachable
-- ---------------------------------------------------------------------------

create policy save_topics_select on public.save_topics for select to authenticated
  using (public.has_save_role(save_id, 'viewer'));
create policy save_topics_write on public.save_topics for all to authenticated
  using (public.has_save_role(save_id, 'member'))
  with check (public.has_save_role(save_id, 'member') and public.has_topic_role(topic_id, 'member'));

create policy topic_edges_select on public.topic_edges for select to authenticated
  using (public.has_topic_role(from_topic, 'viewer'));
create policy topic_edges_write on public.topic_edges for all to authenticated
  using (public.has_topic_role(from_topic, 'member'))
  with check (public.has_topic_role(from_topic, 'member') and public.has_topic_role(to_topic, 'member'));

-- ---------------------------------------------------------------------------
-- Action events are an append-only log: they feed the Save-to-Action score
-- ---------------------------------------------------------------------------

create policy action_events_select on public.action_events for select to authenticated
  using (public.has_task_role(task_id, 'viewer'));
create policy action_events_insert on public.action_events for insert to authenticated
  with check (public.has_task_role(task_id, 'member'));

-- ---------------------------------------------------------------------------
-- Conversations are private to their author, even in a shared workspace
-- ---------------------------------------------------------------------------

create policy conversations_own on public.conversations for all to authenticated
  using (user_id = (select auth.uid()) and public.has_workspace_role(workspace_id, 'viewer'))
  with check (user_id = (select auth.uid()) and public.has_workspace_role(workspace_id, 'viewer'));

create policy messages_own on public.messages for all to authenticated
  using (exists (
    select 1 from public.conversations c where c.id = conversation_id
  ))
  with check (exists (
    select 1 from public.conversations c where c.id = conversation_id
  ));

-- ---------------------------------------------------------------------------
-- Calendar: the workspace can see events, only their owner can change them
-- ---------------------------------------------------------------------------

create policy calendar_events_select on public.calendar_events for select to authenticated
  using (public.has_workspace_role(workspace_id, 'viewer'));
create policy calendar_events_write on public.calendar_events for all to authenticated
  using (user_id = (select auth.uid()) and public.has_workspace_role(workspace_id, 'viewer'))
  with check (user_id = (select auth.uid()) and public.has_workspace_role(workspace_id, 'viewer'));

-- ---------------------------------------------------------------------------
-- Insights are private to their user and written only by agents (service role)
-- ---------------------------------------------------------------------------

create policy insights_select on public.insights for select to authenticated
  using (user_id = (select auth.uid()) and public.has_workspace_role(workspace_id, 'viewer'));

-- jobs, agent_runs, api_keys and connected_accounts deliberately have no policies:
-- with RLS on they are reachable only through the API's service role.
