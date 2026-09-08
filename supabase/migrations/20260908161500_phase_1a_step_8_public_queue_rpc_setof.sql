-- PostgREST must receive queue RPCs as row sets so the worker gets
-- execution rows directly instead of composite/scalar wrapper objects.
-- The worker uses the service_role key, so these RPCs are intentionally
-- restricted to service_role.

drop function if exists public.claim_next_execution();
drop function if exists public.complete_execution(uuid, text, jsonb, text);

create function public.claim_next_execution()
returns setof public.executions
language plpgsql
security definer
set search_path = ''
as $$
declare
  claimed public.executions;
begin
  select * into claimed
  from public.executions
  where status = 'queued'
  order by created_at
  for update skip locked
  limit 1;

  if claimed.id is null then
    return;
  end if;

  update public.executions
  set status = 'running',
      started_at = coalesce(started_at, now()),
      updated_at = now()
  where id = claimed.id
  returning * into claimed;

  return next claimed;
end;
$$;

create function public.complete_execution(
  target_execution_id uuid,
  target_status text,
  target_result jsonb default null,
  target_error text default null
)
returns setof public.executions
language plpgsql
security definer
set search_path = ''
as $$
declare
  completed public.executions;
begin
  if target_status not in ('passed','failed','cancelled') then
    raise exception 'invalid terminal status';
  end if;

  update public.executions
  set status = target_status,
      result = target_result,
      error = target_error,
      finished_at = now(),
      updated_at = now()
  where id = target_execution_id
  returning * into completed;

  if completed.id is not null then
    return next completed;
  end if;
end;
$$;

revoke all on function public.claim_next_execution() from public, anon, authenticated;
revoke all on function public.complete_execution(uuid, text, jsonb, text) from public, anon, authenticated;
grant execute on function public.claim_next_execution() to service_role;
grant execute on function public.complete_execution(uuid, text, jsonb, text) to service_role;

notify pgrst, 'reload schema';
