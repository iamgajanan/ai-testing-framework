create extension if not exists pgcrypto;

create table public.project_api_keys (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  name text not null check (char_length(trim(name)) between 1 and 120),
  key_prefix text not null unique,
  key_hash text not null unique,
  scopes jsonb not null default '["executions:read","executions:write","artifacts:read"]'::jsonb,
  last_used_at timestamptz,
  revoked_at timestamptz,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now()
);

create index project_api_keys_project_idx on public.project_api_keys(project_id, created_at desc);
create index project_api_keys_hash_idx on public.project_api_keys(key_hash);

alter table public.project_api_keys enable row level security;
revoke all on table public.project_api_keys from anon, authenticated;
grant select, insert, update on table public.project_api_keys to authenticated;

create policy "members can view project api keys"
on public.project_api_keys for select to authenticated
using (private.has_org_role(organization_id, array['owner','admin','member']));

create policy "admins can create project api keys"
on public.project_api_keys for insert to authenticated
with check (
  (select auth.uid()) = created_by
  and private.has_org_role(organization_id, array['owner','admin'])
  and exists (select 1 from public.projects p where p.id = project_id and p.organization_id = project_api_keys.organization_id)
);

create policy "admins can revoke project api keys"
on public.project_api_keys for update to authenticated
using (private.has_org_role(organization_id, array['owner','admin']))
with check (private.has_org_role(organization_id, array['owner','admin']));

create table public.execution_artifacts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  execution_id uuid not null references public.executions(id) on delete cascade,
  name text not null check (char_length(trim(name)) between 1 and 255),
  storage_path text not null unique,
  content_type text not null default 'application/octet-stream',
  size_bytes bigint not null default 0 check (size_bytes >= 0),
  created_at timestamptz not null default now()
);

create index execution_artifacts_execution_idx on public.execution_artifacts(execution_id, created_at);
create index execution_artifacts_project_idx on public.execution_artifacts(project_id, created_at desc);

alter table public.execution_artifacts enable row level security;
revoke all on table public.execution_artifacts from anon, authenticated;
grant select on table public.execution_artifacts to authenticated;

create policy "members can view execution artifacts"
on public.execution_artifacts for select to authenticated
using (private.has_org_role(organization_id, array['owner','admin','member']));

insert into storage.buckets (id, name, public, file_size_limit)
values ('execution-artifacts', 'execution-artifacts', false, 524288000)
on conflict (id) do update set public = false, file_size_limit = 524288000;
