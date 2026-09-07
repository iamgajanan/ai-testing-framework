create table public.executions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  requested_by uuid not null references auth.users(id) on delete restrict,
  status text not null default 'queued' check (status in ('queued','running','passed','failed','cancelled')),
  suite_path text not null,
  base_url text not null default '',
  browser text not null default 'chromium' check (browser in ('chromium','firefox','webkit')),
  test_id text,
  output_dir text not null default 'reports',
  formats jsonb not null default '["html","json"]'::jsonb,
  workers integer not null default 1 check (workers between 1 and 64),
  config jsonb,
  ai_provider text,
  metadata jsonb not null default '{}'::jsonb,
  result jsonb,
  error text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz not null default now()
);

create index executions_org_created_idx on public.executions(organization_id, created_at desc);
create index executions_project_created_idx on public.executions(project_id, created_at desc);
create index executions_status_created_idx on public.executions(status, created_at);

alter table public.executions enable row level security;
revoke all on table public.executions from anon, authenticated;
grant select, insert on table public.executions to authenticated;

create policy "organization members can view executions"
on public.executions for select to authenticated
using (private.has_org_role(organization_id, array['owner','admin','member']));

create policy "organization members can create executions"
on public.executions for insert to authenticated
with check (
  (select auth.uid()) = requested_by
  and private.has_org_role(organization_id, array['owner','admin','member'])
  and exists (
    select 1 from public.projects p
    where p.id = project_id and p.organization_id = executions.organization_id
  )
);

create or replace function private.claim_next_execution()
returns public.executions
language plpgsql security definer set search_path = ''
as $$
declare claimed public.executions;
begin
  select * into claimed from public.executions
  where status = 'queued' order by created_at for update skip locked limit 1;
  if claimed.id is null then return null; end if;
  update public.executions
  set status = 'running', started_at = coalesce(started_at, now()), updated_at = now()
  where id = claimed.id returning * into claimed;
  return claimed;
end;
$$;

revoke all on function private.claim_next_execution() from public, authenticated;

create or replace function private.complete_execution(
  target_execution_id uuid,
  target_status text,
  target_result jsonb default null,
  target_error text default null
)
returns public.executions
language plpgsql security definer set search_path = ''
as $$
declare completed public.executions;
begin
  if target_status not in ('passed','failed','cancelled') then
    raise exception 'invalid terminal status';
  end if;
  update public.executions
  set status = target_status, result = target_result, error = target_error,
      finished_at = now(), updated_at = now()
  where id = target_execution_id returning * into completed;
  return completed;
end;
$$;

revoke all on function private.complete_execution(uuid, text, jsonb, text) from public, authenticated;

create trigger executions_set_updated_at
before update on public.executions
for each row execute function private.set_updated_at();
