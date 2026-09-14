'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

interface Props {
  suiteId: string
  projectId: string
  currentName: string
}

export function SuiteActions({ suiteId, projectId, currentName }: Props) {
  const router = useRouter()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(currentName)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function rename() {
    if (!name.trim() || name === currentName) { setEditing(false); return }
    setSaving(true); setError(null)
    try {
      const res = await fetch(`/api/suites/${suiteId}?project_id=${projectId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail ?? 'Rename failed')
      }
      setEditing(false)
      router.refresh()
    } catch (e: any) {
      setError(String(e.message ?? e))
    } finally {
      setSaving(false)
    }
  }

  async function deleteSuite() {
    setDeleting(true); setError(null)
    try {
      const res = await fetch(`/api/suites/${suiteId}?project_id=${projectId}`, {
        method: 'DELETE',
      })
      if (!res.ok && res.status !== 204) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail ?? 'Delete failed')
      }
      router.push('/dashboard/suites')
    } catch (e: any) {
      setError(String(e.message ?? e))
      setDeleting(false)
    }
  }

  return (
    <div className="card" style={{ padding: '12px 16px' }}>
      {error && <div className="notice error" style={{ marginBottom: 10 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        {editing ? (
          <>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') rename(); if (e.key === 'Escape') setEditing(false) }}
              autoFocus
              style={{ flex: 1, minWidth: 200 }}
            />
            <button className="btn btn-primary" onClick={rename} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button className="btn" onClick={() => { setEditing(false); setName(currentName) }}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button className="btn" onClick={() => setEditing(true)}>✏ Rename</button>
            {!confirmDelete ? (
              <button
                className="btn"
                style={{ color: '#ef4444', borderColor: '#fca5a5' }}
                onClick={() => setConfirmDelete(true)}
              >
                🗑 Delete suite
              </button>
            ) : (
              <>
                <span style={{ fontSize: 12, color: '#ef4444' }}>
                  Delete all versions? This cannot be undone.
                </span>
                <button
                  className="btn"
                  style={{ background: '#ef4444', color: '#fff', border: 'none' }}
                  onClick={deleteSuite}
                  disabled={deleting}
                >
                  {deleting ? 'Deleting…' : 'Yes, delete'}
                </button>
                <button className="btn" onClick={() => setConfirmDelete(false)}>Cancel</button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
