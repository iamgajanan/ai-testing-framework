create table if not exists public.test_suites (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  name text not null,
  slug text not null,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(project_id, slug)
);
create table if not exists public.test_suite_versions (
  id uuid primary key default gen_random_uuid(),
  test_suite_id uuid not null references public.test_suites(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  version integer not null,
  storage_path text not null unique,
  filename text not null,
  content_type text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  sha256 text not null,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique(test_suite_id, version)
);
create index if not exists test_suites_org_idx on public.test_suites(organization_id);
create index if not exists test_suites_project_idx on public.test_suites(project_id);
create index if not exists test_suite_versions_suite_idx on public.test_suite_versions(test_suite_id, version desc);
alter table public.test_suites enable row level security;
alter table public.test_suite_versions enable row level security;
drop policy if exists test_suites_member_select on public.test_suites;
create policy test_suites_member_select on public.test_suites for select to authenticated using (exists (select 1 from public.organization_members m where m.organization_id = test_suites.organization_id and m.user_id = auth.uid()));
drop policy if exists test_suites_member_insert on public.test_suites;
create policy test_suites_member_insert on public.test_suites for insert to authenticated with check (created_by = auth.uid() and exists (select 1 from public.organization_members m where m.organization_id = test_suites.organization_id and m.user_id = auth.uid()) and exists (select 1 from public.projects p where p.id = test_suites.project_id and p.organization_id = test_suites.organization_id));
drop policy if exists test_suite_versions_member_select on public.test_suite_versions;
create policy test_suite_versions_member_select on public.test_suite_versions for select to authenticated using (exists (select 1 from public.organization_members m where m.organization_id = test_suite_versions.organization_id and m.user_id = auth.uid()));
drop policy if exists test_suite_versions_member_insert on public.test_suite_versions;
create policy test_suite_versions_member_insert on public.test_suite_versions for insert to authenticated with check (created_by = auth.uid() and exists (select 1 from public.organization_members m where m.organization_id = test_suite_versions.organization_id and m.user_id = auth.uid()) and exists (select 1 from public.test_suites s where s.id = test_suite_versions.test_suite_id and s.project_id = test_suite_versions.project_id and s.organization_id = test_suite_versions.organization_id));
create or replace function public.touch_test_suite_updated_at() returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
drop trigger if exists test_suites_updated_at on public.test_suites;
create trigger test_suites_updated_at before update on public.test_suites for each row execute function public.touch_test_suite_updated_at();
insert into storage.buckets (id, name, public) values ('test-suites', 'test-suites', false) on conflict (id) do update set public = false;
