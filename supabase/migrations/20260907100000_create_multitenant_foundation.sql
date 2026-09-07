create schema if not exists private;

create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(trim(name)) >= 2),
  slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.organization_members (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'member')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, user_id)
);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null check (char_length(trim(name)) >= 2),
  slug text not null check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, slug)
);

create index organization_members_user_id_idx on public.organization_members(user_id);
create index organization_members_organization_id_idx on public.organization_members(organization_id);
create index projects_organization_id_idx on public.projects(organization_id);

create or replace function private.has_org_role(target_organization_id uuid, allowed_roles text[])
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.organization_members m
    where m.organization_id = target_organization_id
      and m.user_id = (select auth.uid())
      and m.role = any(allowed_roles)
  );
$$;

revoke all on function private.has_org_role(uuid, text[]) from public;
grant usage on schema private to authenticated;
grant execute on function private.has_org_role(uuid, text[]) to authenticated;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger organizations_set_updated_at
before update on public.organizations
for each row execute function private.set_updated_at();

create trigger organization_members_set_updated_at
before update on public.organization_members
for each row execute function private.set_updated_at();

create trigger projects_set_updated_at
before update on public.projects
for each row execute function private.set_updated_at();

create or replace function private.add_organization_owner()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.organization_members (organization_id, user_id, role)
  values (new.id, new.created_by, 'owner');
  return new;
end;
$$;

revoke all on function private.add_organization_owner() from public;

create trigger organizations_add_owner
  after insert on public.organizations
  for each row execute function private.add_organization_owner();

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.projects enable row level security;

revoke all on table public.organizations from anon, authenticated;
revoke all on table public.organization_members from anon, authenticated;
revoke all on table public.projects from anon, authenticated;

grant select, insert, update, delete on table public.organizations to authenticated;
grant select, insert, update, delete on table public.organization_members to authenticated;
grant select, insert, update, delete on table public.projects to authenticated;

create policy "organization members can view organizations"
on public.organizations for select
to authenticated
using (private.has_org_role(id, array['owner','admin','member']));

create policy "users can create organizations"
on public.organizations for insert
to authenticated
with check ((select auth.uid()) = created_by);

create policy "organization owners and admins can update organizations"
on public.organizations for update
to authenticated
using (private.has_org_role(id, array['owner','admin']))
with check (private.has_org_role(id, array['owner','admin']));

create policy "organization owners can delete organizations"
on public.organizations for delete
to authenticated
using (private.has_org_role(id, array['owner']));

create policy "organization members can view membership"
on public.organization_members for select
to authenticated
using (private.has_org_role(organization_id, array['owner','admin','member']));

create policy "owners and admins can add members"
on public.organization_members for insert
to authenticated
with check (
  (select auth.uid()) = user_id
  and (
    exists (
      select 1 from public.organizations o
      where o.id = organization_id and o.created_by = (select auth.uid())
    )
    or private.has_org_role(organization_id, array['owner','admin'])
  )
);

create policy "owners and admins can update members"
on public.organization_members for update
to authenticated
using (private.has_org_role(organization_id, array['owner','admin']))
with check (private.has_org_role(organization_id, array['owner','admin']));

create policy "owners and admins can remove members"
on public.organization_members for delete
to authenticated
using (private.has_org_role(organization_id, array['owner','admin']));

create policy "organization members can view projects"
on public.projects for select
to authenticated
using (private.has_org_role(organization_id, array['owner','admin','member']));

create policy "organization members can create projects"
on public.projects for insert
to authenticated
with check (
  (select auth.uid()) = created_by
  and private.has_org_role(organization_id, array['owner','admin','member'])
);

create policy "organization members can update projects"
on public.projects for update
to authenticated
using (private.has_org_role(organization_id, array['owner','admin','member']))
with check (private.has_org_role(organization_id, array['owner','admin','member']));

create policy "organization admins can delete projects"
on public.projects for delete
to authenticated
using (private.has_org_role(organization_id, array['owner','admin']));
