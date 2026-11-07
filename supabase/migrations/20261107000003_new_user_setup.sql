-- Every new account gets a profile and a personal workspace, in the same
-- transaction as the signup. The owner membership comes from the
-- add_owner_as_member trigger on workspaces.

create function public.handle_new_user() returns trigger
language plpgsql security definer
set search_path = ''
as $$
declare
  metadata jsonb := coalesce(new.raw_user_meta_data, '{}');
begin
  insert into public.profiles (user_id, name, avatar_url)
  values (
    new.id,
    -- Google sends full_name; email signups send the name from our form.
    coalesce(
      nullif(metadata ->> 'full_name', ''),
      nullif(metadata ->> 'name', ''),
      split_part(new.email, '@', 1)
    ),
    nullif(metadata ->> 'avatar_url', '')
  );

  insert into public.workspaces (name, type, owner_id)
  values ('Personal', 'personal', new.id);

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
