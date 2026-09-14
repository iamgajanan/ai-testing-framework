'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

interface Project {
  id: string
  name: string
}

interface Props {
  projects: Project[]
  organizationId: string
}

const EXAMPLE_PROMPTS = [
  'Test SauceDemo login, verify products are displayed, add a backpack to cart, and complete checkout.',
  'Open the homepage, verify the navigation links work, and check that the main heading is visible.',
  'Test the search form — enter a query, submit it, and verify results appear on the page.',
  'Verify the login form — check that required fields show validation errors when empty.',
]

export function GenerateForm({ projects, organizationId }: Props) {
  const router = useRouter()
  const [prompt, setPrompt] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [browser, setBrowser] = useState('chromium')
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '')
  const [step, setStep] = useState<'input' | 'generating' | 'preview' | 'done'>('input')
  const [saving, setSaving] = useState(false)
  const [generated, setGenerated] = useState<any>(null)
  const [editedSuite, setEditedSuite] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [savedSuiteId, setSavedSuiteId] = useState<string | null>(null)

  async function generate() {
    if (!prompt.trim() || !baseUrl.trim()) return
    setError(null)
    setStep('generating')
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, base_url: baseUrl, browser, project_id: projectId, organization_id: organizationId }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? data.error ?? 'Generation failed')
      setGenerated(data)
      setEditedSuite(JSON.stringify(data.suite, null, 2))
      setStep('preview')
    } catch (e: any) {
      setError(String(e.message ?? e))
      setStep('input')
    }
  }

  async function saveSuite() {
    setError(null)
    setSaving(true)
    let suite: any
    try {
      suite = JSON.parse(editedSuite)
    } catch {
      setError('Invalid JSON — fix the suite before saving.')
      setSaving(false)
      return
    }
    try {
      // Upload the suite as a new test-suite version
      const blob = new Blob([JSON.stringify(suite, null, 2)], { type: 'application/json' })
      const suiteName = suite.test_suite ?? `Generated suite`
      const fd = new FormData()
      fd.append('file', blob, `generated-suite-${Date.now()}.json`)
      fd.append('name', suiteName)
      const res = await fetch(`/api/suites?project_id=${projectId}`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? data.error ?? 'Save failed')
      setSavedSuiteId(data.test_suite_id ?? data.id)
      setSaving(false)
      setStep('done')
    } catch (e: any) {
      setError(String(e.message ?? e))
      setSaving(false)
    }
  }

  function runNow() {
    router.push(`/dashboard/executions?suite=${savedSuiteId}`)
  }

  if (step === 'done') {
    return (
      <div className="card" style={{ textAlign: 'center', padding: 40 }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
        <h2 style={{ marginBottom: 8 }}>Suite saved</h2>
        <p style={{ color: 'var(--muted)', marginBottom: 24 }}>
          Your generated test suite has been saved and is ready to run.
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={runNow}>
            Run it now →
          </button>
          <button className="btn" onClick={() => { setStep('input'); setGenerated(null); setPrompt(''); setBaseUrl('') }}>
            Generate another
          </button>
          <a className="btn" href="/dashboard/suites">View all suites</a>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: step === 'preview' ? '1fr 1fr' : '1fr', gap: 16 }}>
      {/* Left: input form */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card">
          <div className="panel-kicker" style={{ marginBottom: 12 }}>GENERATION INPUT</div>

          {!projects.length && (
            <div className="notice error" style={{ marginBottom: 16 }}>
              Create a project first before generating suites.
            </div>
          )}

          {error && (
            <div className="notice error" style={{ marginBottom: 16 }}>
              {error}
            </div>
          )}

          <div className="field" style={{ marginBottom: 12 }}>
            <label>Natural-language prompt</label>
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="Describe what you want to test in plain English…"
              rows={4}
              style={{ width: '100%', resize: 'vertical', fontFamily: 'inherit', fontSize: 13, padding: '8px 10px', background: 'var(--surface-2)', border: '1px solid var(--line-soft)', borderRadius: 6, color: 'inherit' }}
              disabled={step !== 'input'}
            />
          </div>

          <div className="field" style={{ marginBottom: 12 }}>
            <label>Target URL</label>
            <input
              type="url"
              value={baseUrl}
              onChange={e => setBaseUrl(e.target.value)}
              placeholder="https://example.com"
              disabled={step !== 'input'}
            />
            <small style={{ color: 'var(--muted)', fontSize: 11 }}>
              The URL the AI will inspect to ground selectors in real DOM elements.
            </small>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div className="field">
              <label>Project</label>
              <select value={projectId} onChange={e => setProjectId(e.target.value)} disabled={step !== 'input'}>
                {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Browser</label>
              <select value={browser} onChange={e => setBrowser(e.target.value)} disabled={step !== 'input'}>
                <option value="chromium">Chromium</option>
                <option value="firefox">Firefox</option>
                <option value="webkit">WebKit</option>
              </select>
            </div>
          </div>

          <button
            className="btn btn-primary"
            onClick={generate}
            disabled={step !== 'input' || !prompt.trim() || !baseUrl.trim() || !projects.length}
            style={{ width: '100%' }}
          >
            {step === 'generating' ? '⏳ Generating…' : '✦ Generate test suite'}
          </button>
        </div>

        {/* Example prompts */}
        {step === 'input' && (
          <div className="card">
            <div className="panel-kicker" style={{ marginBottom: 10 }}>EXAMPLE PROMPTS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {EXAMPLE_PROMPTS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => setPrompt(p)}
                  style={{
                    textAlign: 'left',
                    background: 'var(--surface-2)',
                    border: '1px solid var(--line-soft)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    fontSize: 12,
                    color: 'var(--muted)',
                    cursor: 'pointer',
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right: preview + editor */}
      {step === 'preview' && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div className="panel-kicker">GENERATED SUITE</div>
              <p style={{ fontSize: 12, color: 'var(--muted)', margin: '4px 0 0' }}>
                Review and edit the JSON before saving. Selectors are grounded in the real page DOM.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn" onClick={() => setStep('input')}>← Edit prompt</button>
              <button className="btn btn-primary" onClick={saveSuite}>
                {saving ? 'Saving…' : 'Save suite →'}
              </button>
            </div>
          </div>

          {error && <div className="notice error">{error}</div>}

          <textarea
            value={editedSuite}
            onChange={e => setEditedSuite(e.target.value)}
            style={{
              flex: 1,
              minHeight: 480,
              fontFamily: 'monospace',
              fontSize: 11,
              lineHeight: 1.6,
              padding: 12,
              background: '#080e18',
              color: '#9eabc0',
              border: '1px solid var(--line-soft)',
              borderRadius: 6,
              resize: 'vertical',
            }}
            spellCheck={false}
          />

          <div style={{ fontSize: 11, color: 'var(--muted)' }}>
            ✏️ Edit steps, selectors, or validations above before saving.
            The suite will be saved as a new version in your project.
          </div>
        </div>
      )}
    </div>
  )
}
