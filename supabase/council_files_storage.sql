-- Private Council file storage for AInimity.
-- Run once in Supabase Dashboard → SQL Editor.
-- A 20 MiB limit matches the frontend upload guard.

insert into storage.buckets (id, name, public, file_size_limit)
values ('council-documents', 'council-documents', false, 20971520)
on conflict (id) do update
set name = excluded.name,
    public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = null;

drop policy if exists "Council files: owner can upload" on storage.objects;
drop policy if exists "Council files: owner can read" on storage.objects;
drop policy if exists "Council files: owner can remove" on storage.objects;

create policy "Council files: owner can upload"
on storage.objects for insert to authenticated
with check (
  bucket_id = 'council-documents'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy "Council files: owner can read"
on storage.objects for select to authenticated
using (
  bucket_id = 'council-documents'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

create policy "Council files: owner can remove"
on storage.objects for delete to authenticated
using (
  bucket_id = 'council-documents'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);
