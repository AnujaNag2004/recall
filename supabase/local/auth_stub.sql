-- Minimal stand-in for what a real Supabase project already provides, so the
-- migrations can run on plain Postgres (docker-compose and the migration tests).
-- NEVER run this against a Supabase project.

create schema if not exists extensions;
create schema if not exists auth;

create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;

create table auth.users (
  id uuid primary key default gen_random_uuid(),
  email text unique
);

-- Same contract as Supabase: the user id comes from the request's JWT claims.
create function auth.uid() returns uuid
language sql stable
as $$
  select (nullif(current_setting('request.jwt.claims', true), '')::json ->> 'sub')::uuid
$$;

grant usage on schema public, auth, extensions to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;

-- Supabase's default privileges: access is then narrowed by RLS and the migrations.
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on functions to anon, authenticated, service_role;
