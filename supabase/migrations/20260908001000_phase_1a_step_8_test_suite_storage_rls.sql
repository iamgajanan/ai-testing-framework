drop policy if exists "test_suites_object_member_insert" on storage.objects;
create policy "test_suites_object_member_insert"
on storage.objects
for insert to authenticated
with check (
  bucket_id = 'test-suites'
  and exists (
    select 1
    from public.projects p
    join public.organization_members m on m.organization_id = p.organization_id
    where p.id = ((storage.foldername(name))[2])::uuid
      and p.organization_id = ((storage.foldername(name))[1])::uuid
      and m.user_id = (select auth.uid())
  )
);

drop policy if exists "test_suites_object_member_select" on storage.objects;
create policy "test_suites_object_member_select"
on storage.objects
for select to authenticated
using (
  bucket_id = 'test-suites'
  and exists (
    select 1
    from public.projects p
    join public.organization_members m on m.organization_id = p.organization_id
    where p.id = ((storage.foldername(name))[2])::uuid
      and p.organization_id = ((storage.foldername(name))[1])::uuid
      and m.user_id = (select auth.uid())
  )
);
