import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { apiFetch } from '@/lib/api'

export default async function VersionDownloadPage({
  params,
}: {
  params: Promise<{ suiteId: string; version: string }>
}) {
  const { suiteId, version } = await params
  const supabase = await createClient()
  const { data: claims } = await supabase.auth.getClaims()
  if (!claims?.claims?.sub) redirect('/login')

  // Get the suite to find its project
  const { data: suite } = await supabase
    .from('test_suites')
    .select('project_id')
    .eq('id', suiteId)
    .single()

  if (!suite) redirect('/dashboard/suites')

  // Get a signed download URL from the API
  const res = await apiFetch(
    `/v1/projects/${suite.project_id}/test-suites/${suiteId}/versions/${version}?expires_in=300`,
  )

  if (res.ok && res.data?.signed_url) {
    redirect(res.data.signed_url)
  }

  redirect(`/dashboard/suites/${suiteId}`)
}
