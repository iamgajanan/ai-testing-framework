begin;

select plan(6);

select has_table('public', 'organizations');
select has_table('public', 'organization_members');
select has_table('public', 'projects');

select ok(
  (select relrowsecurity from pg_class where oid = 'public.organizations'::regclass),
  'organizations has RLS enabled'
);
select ok(
  (select relrowsecurity from pg_class where oid = 'public.organization_members'::regclass),
  'organization_members has RLS enabled'
);
select ok(
  (select relrowsecurity from pg_class where oid = 'public.projects'::regclass),
  'projects has RLS enabled'
);

select * from finish();
rollback;
