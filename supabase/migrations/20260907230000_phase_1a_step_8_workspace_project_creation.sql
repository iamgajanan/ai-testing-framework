create or replace function public.create_workspace_project(workspace_name text, project_name text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  workspace_slug text;
  project_slug text;
  org_id uuid;
  new_project_id uuid;
  base_slug text;
  suffix integer := 2;
begin
  if uid is null then raise exception 'Authentication required' using errcode = '42501'; end if;
  if workspace_name is null or char_length(trim(workspace_name)) < 2 or char_length(trim(workspace_name)) > 120 then raise exception 'Workspace name must be between 2 and 120 characters' using errcode = '22023'; end if;
  if project_name is null or char_length(trim(project_name)) < 2 or char_length(trim(project_name)) > 120 then raise exception 'Project name must be between 2 and 120 characters' using errcode = '22023'; end if;

  workspace_slug := lower(regexp_replace(trim(workspace_name), '[^a-z0-9]+', '-', 'g'));
  workspace_slug := trim(both '-' from workspace_slug);
  if workspace_slug = '' then workspace_slug := 'workspace'; end if;
  workspace_slug := left(workspace_slug, 80);

  select o.id into org_id
  from public.organizations o
  join public.organization_members m on m.organization_id = o.id
  where m.user_id = uid
  order by o.created_at asc limit 1;

  if org_id is null then
    begin
      insert into public.organizations(name, slug, created_by)
      values(trim(workspace_name), workspace_slug, uid)
      returning id into org_id;
    exception when unique_violation then
      select o.id into org_id from public.organizations o where o.slug = workspace_slug and o.created_by = uid limit 1;
      if org_id is null then raise; end if;
    end;
  end if;

  base_slug := lower(regexp_replace(trim(project_name), '[^a-z0-9]+', '-', 'g'));
  base_slug := trim(both '-' from base_slug);
  if base_slug = '' then base_slug := 'project'; end if;
  base_slug := left(base_slug, 80);
  project_slug := base_slug;
  while exists(select 1 from public.projects p where p.organization_id = org_id and p.slug = project_slug) loop
    project_slug := left(base_slug, 77) || '-' || suffix::text;
    suffix := suffix + 1;
  end loop;

  insert into public.projects(organization_id, name, slug, created_by)
  values(org_id, trim(project_name), project_slug, uid)
  returning id into new_project_id;

  return jsonb_build_object('id', new_project_id, 'organization_id', org_id, 'name', trim(project_name), 'slug', project_slug);
end;
$$;

revoke all on function public.create_workspace_project(text, text) from public, anon;
grant execute on function public.create_workspace_project(text, text) to authenticated;
