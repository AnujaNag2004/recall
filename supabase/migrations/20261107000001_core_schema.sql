-- Core schema: every table from the data model.
-- Row-level security is added in the next migration.

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

create type public.workspace_type as enum ('personal', 'team');

-- Declared lowest to highest on purpose: Postgres compares enums in declaration
-- order, so "role >= 'member'" means "member or above".
create type public.workspace_role as enum ('viewer', 'member', 'admin', 'owner');

create type public.save_mode as enum ('life', 'study', 'work');
create type public.save_status as enum ('pending', 'processing', 'ready', 'failed');
create type public.intent_source as enum ('user', 'inferred');
create type public.entity_type as enum (
  'tool', 'website', 'book', 'course', 'product', 'repo', 'place', 'person', 'other'
);
create type public.resource_pricing as enum ('free', 'paid', 'freemium', 'unknown');
create type public.task_type as enum ('micro_action', 'action_item', 'checklist_item');
create type public.task_status as enum ('suggested', 'accepted', 'done', 'skipped', 'let_go');
create type public.task_size as enum ('tiny', 'small', 'medium');
create type public.action_event_type as enum (
  'suggested', 'accepted', 'done', 'skipped', 'rescheduled', 'let_go'
);
create type public.message_role as enum ('user', 'assistant', 'system');
create type public.calendar_source as enum ('internal', 'google');
create type public.insight_kind as enum ('weekly_digest', 'reflection');
create type public.job_status as enum ('queued', 'running', 'succeeded', 'failed');
create type public.agent_run_status as enum ('running', 'succeeded', 'failed');

-- ---------------------------------------------------------------------------
-- Users and workspaces
-- ---------------------------------------------------------------------------

create table public.profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users (id) on delete cascade,
  name text,
  avatar_url text,
  timezone text not null default 'UTC',
  preferences jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type public.workspace_type not null default 'personal',
  owner_id uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index workspaces_owner_id_idx on public.workspaces (owner_id);

create table public.workspace_members (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role public.workspace_role not null default 'member',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, user_id)
);
create index workspace_members_user_id_idx on public.workspace_members (user_id);

create table public.invites (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  email text not null,
  token text not null unique,
  role public.workspace_role not null default 'member',
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index invites_workspace_id_idx on public.invites (workspace_id);

-- ---------------------------------------------------------------------------
-- Saves and what the ingestion graph derives from them
-- ---------------------------------------------------------------------------

create table public.saves (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  created_by uuid references auth.users (id) on delete set null,
  source_url text,
  source_type text not null,
  title text,
  author text,
  thumbnail_url text,
  embed_html text,
  mode public.save_mode,
  status public.save_status not null default 'pending',
  intent text,
  intent_source public.intent_source,
  summary text,
  key_points jsonb not null default '[]',
  content_template text,
  raw_text text,
  storage_path text,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- Target of the composite foreign keys below, which guarantee that a row
  -- attached to a save can never carry a different workspace_id than the save.
  unique (id, workspace_id)
);
create index saves_workspace_created_idx on public.saves (workspace_id, created_at desc);
create index saves_workspace_status_idx on public.saves (workspace_id, status);

create table public.save_chunks (
  id uuid primary key default gen_random_uuid(),
  save_id uuid not null,
  workspace_id uuid not null,
  chunk_index integer not null,
  "text" text not null,
  start_ts double precision,
  end_ts double precision,
  -- Must match EMBEDDING_DIM in the API config. Changing the embedding model's
  -- dimension requires a new migration and re-embedding.
  embedding extensions.vector(768),
  tsv tsvector generated always as (to_tsvector('english', "text")) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (save_id, chunk_index),
  foreign key (save_id, workspace_id) references public.saves (id, workspace_id) on delete cascade
);
create index save_chunks_workspace_idx on public.save_chunks (workspace_id);
create index save_chunks_embedding_idx on public.save_chunks
  using hnsw (embedding extensions.vector_cosine_ops);
create index save_chunks_tsv_idx on public.save_chunks using gin (tsv);

create table public.transcript_segments (
  id uuid primary key default gen_random_uuid(),
  save_id uuid not null references public.saves (id) on delete cascade,
  start_ts double precision not null,
  end_ts double precision,
  "text" text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index transcript_segments_save_idx on public.transcript_segments (save_id, start_ts);

create table public.entities (
  id uuid primary key default gen_random_uuid(),
  save_id uuid not null references public.saves (id) on delete cascade,
  name text not null,
  type public.entity_type not null default 'other',
  mention_ts double precision,
  context text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index entities_save_idx on public.entities (save_id);

create table public.resources (
  id uuid primary key default gen_random_uuid(),
  entity_id uuid references public.entities (id) on delete cascade,
  save_id uuid not null references public.saves (id) on delete cascade,
  url text not null,
  domain text not null,
  title text,
  description text,
  favicon_url text,
  pricing public.resource_pricing not null default 'unknown',
  category text,
  confidence double precision not null default 0 check (confidence between 0 and 1),
  verified boolean not null default false,
  last_checked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index resources_save_idx on public.resources (save_id);
create index resources_entity_idx on public.resources (entity_id);

-- ---------------------------------------------------------------------------
-- Knowledge graph
-- ---------------------------------------------------------------------------

create table public.topics (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  name text not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, name)
);

create table public.save_topics (
  id uuid primary key default gen_random_uuid(),
  save_id uuid not null references public.saves (id) on delete cascade,
  topic_id uuid not null references public.topics (id) on delete cascade,
  weight double precision not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (save_id, topic_id)
);
create index save_topics_topic_idx on public.save_topics (topic_id);

create table public.topic_edges (
  id uuid primary key default gen_random_uuid(),
  from_topic uuid not null references public.topics (id) on delete cascade,
  to_topic uuid not null references public.topics (id) on delete cascade,
  relation text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (from_topic, to_topic, relation),
  check (from_topic <> to_topic)
);
create index topic_edges_to_topic_idx on public.topic_edges (to_topic);

-- ---------------------------------------------------------------------------
-- Save-to-Action Engine
-- ---------------------------------------------------------------------------

create table public.tasks (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  save_id uuid,
  title text not null,
  description text,
  type public.task_type not null default 'micro_action',
  assignee_id uuid references auth.users (id) on delete set null,
  due_at timestamptz,
  scheduled_for timestamptz,
  status public.task_status not null default 'suggested',
  size public.task_size not null default 'tiny',
  followup_at timestamptz,
  completed_at timestamptz,
  source_agent text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- A task outlives its save: deleting the save clears save_id only.
  foreign key (save_id, workspace_id) references public.saves (id, workspace_id)
    on delete set null (save_id)
);
create index tasks_workspace_status_idx on public.tasks (workspace_id, status);
create index tasks_save_idx on public.tasks (save_id);
create index tasks_assignee_idx on public.tasks (assignee_id);
create index tasks_followup_idx on public.tasks (followup_at) where followup_at is not null;

create table public.action_events (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.tasks (id) on delete cascade,
  event public.action_event_type not null,
  "at" timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index action_events_task_idx on public.action_events (task_id, "at");

-- ---------------------------------------------------------------------------
-- Learn mode
-- ---------------------------------------------------------------------------

create table public.flashcards (
  id uuid primary key default gen_random_uuid(),
  save_id uuid,
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  front text not null,
  back text not null,
  ease double precision not null default 2.5,
  interval_days integer not null default 0,
  repetitions integer not null default 0,
  due_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (save_id, workspace_id) references public.saves (id, workspace_id) on delete cascade
);
create index flashcards_review_idx on public.flashcards (workspace_id, due_at);
create index flashcards_save_idx on public.flashcards (save_id);

-- ---------------------------------------------------------------------------
-- Chat
-- ---------------------------------------------------------------------------

create table public.conversations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  -- Set when this is a "chat with this save" thread rather than Ask Your Brain.
  save_id uuid references public.saves (id) on delete cascade,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index conversations_user_idx on public.conversations (user_id, workspace_id, updated_at desc);
create index conversations_workspace_idx on public.conversations (workspace_id);
create index conversations_save_idx on public.conversations (save_id);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations (id) on delete cascade,
  role public.message_role not null,
  content text not null,
  citations jsonb not null default '[]',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index messages_conversation_idx on public.messages (conversation_id, created_at);

-- ---------------------------------------------------------------------------
-- Calendar and insights
-- ---------------------------------------------------------------------------

create table public.calendar_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null,
  starts_at timestamptz not null,
  ends_at timestamptz,
  source public.calendar_source not null default 'internal',
  external_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, source, external_id)
);
create index calendar_events_workspace_idx on public.calendar_events (workspace_id, starts_at);

create table public.insights (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  period_start date not null,
  kind public.insight_kind not null,
  content jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, user_id, period_start, kind)
);
create index insights_user_idx on public.insights (user_id);

-- ---------------------------------------------------------------------------
-- Infrastructure (reached by the API with the service role only)
-- ---------------------------------------------------------------------------

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  type text not null,
  payload jsonb not null default '{}',
  status public.job_status not null default 'queued',
  attempts integer not null default 0,
  run_after timestamptz not null default now(),
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
-- Serves the worker's "next runnable job" query.
create index jobs_runnable_idx on public.jobs (run_after) where status = 'queued';

create table public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  save_id uuid references public.saves (id) on delete set null,
  task_id uuid references public.tasks (id) on delete set null,
  graph text not null,
  status public.agent_run_status not null default 'running',
  trace_id text,
  tokens_in integer,
  tokens_out integer,
  latency_ms integer,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index agent_runs_created_idx on public.agent_runs (created_at desc);
create index agent_runs_save_idx on public.agent_runs (save_id);
create index agent_runs_task_idx on public.agent_runs (task_id);

create table public.api_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  hashed_key text not null unique,
  label text not null,
  last_used_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index api_keys_user_idx on public.api_keys (user_id);

create table public.connected_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  provider text not null,
  -- Fernet-encrypted by the API; plaintext tokens never reach the database.
  encrypted_access_token text,
  encrypted_refresh_token text,
  token_expires_at timestamptz,
  scopes text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, provider)
);

-- ---------------------------------------------------------------------------
-- Keep updated_at current on every table
-- ---------------------------------------------------------------------------

create function public.set_updated_at() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

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
    execute format(
      'create trigger set_updated_at before update on public.%I
       for each row execute function public.set_updated_at()',
      table_name
    );
  end loop;
end;
$$;
