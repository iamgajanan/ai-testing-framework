'use client'

/**
 * ArtifactViewer — client component that renders the correct viewer for each
 * artifact content type:
 *
 *  text/html              → sandboxed iframe (renders HTML reports)
 *  video/webm, video/mp4  → HTML5 <video> with download fallback
 *  image/*                → <img>
 *  application/json       → formatted JSON viewer
 *  text/*                 → plain text viewer
 *  *                      → download card
 */

import { useState } from 'react'

interface ArtifactMeta {
  id: string
  name: string
  storage_path: string
  content_type: string
  size_bytes: number
  signed_url: string
  expires_in?: number
}

interface Props {
  artifact: ArtifactMeta
}

export function ArtifactViewer({ artifact }: Props) {
  const { content_type, signed_url, name } = artifact
  const ct = content_type?.toLowerCase() ?? ''

  if (ct === 'text/html') {
    return <HtmlViewer url={signed_url} name={name} />
  }

  if (ct.startsWith('video/')) {
    return <VideoViewer url={signed_url} contentType={ct} name={name} />
  }

  if (ct.startsWith('image/')) {
    return <ImageViewer url={signed_url} name={name} />
  }

  if (ct === 'application/json' || ct === 'text/json' || name.endsWith('.json')) {
    return <JsonViewer url={signed_url} name={name} />
  }

  if (ct.startsWith('text/')) {
    return <TextViewer url={signed_url} name={name} />
  }

  return <DownloadCard artifact={artifact} />
}

// ---------------------------------------------------------------------------
// HTML viewer — uses a sandboxed iframe
// The signed Supabase URL is fetched server-side and used as the iframe src.
// sandbox="allow-same-origin allow-scripts" lets CSS/JS in the report run
// while still isolating the iframe from the parent page's origin.
// ---------------------------------------------------------------------------
function HtmlViewer({ url, name }: { url: string; name: string }) {
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>📄 {name}</span>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="btn"
          style={{ fontSize: 10, padding: '5px 10px' }}
        >
          Open in new tab ↗
        </a>
      </div>
      <iframe
        src={url}
        title={name}
        sandbox="allow-same-origin allow-scripts allow-popups"
        style={{
          width: '100%',
          height: 680,
          border: 'none',
          display: 'block',
          background: '#fff',
        }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Video viewer — HTML5 player with download fallback
// Supabase signed URLs work directly with browser media requests because
// they are plain HTTPS URLs with no special authentication cookie needed.
// ---------------------------------------------------------------------------
function VideoViewer({
  url,
  contentType,
  name,
}: {
  url: string
  contentType: string
  name: string
}) {
  return (
    <div className="card" style={{ padding: 16 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}
      >
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>🎬 {name}</span>
        <a
          href={url}
          download={name}
          className="btn"
          style={{ fontSize: 10, padding: '5px 10px' }}
        >
          ↓ Download
        </a>
      </div>
      <video
        controls
        style={{
          width: '100%',
          borderRadius: 8,
          background: '#000',
          maxHeight: 500,
        }}
      >
        <source src={url} type={contentType} />
        {/* Fallback for browsers that do not support webm */}
        <p style={{ color: 'var(--muted)', fontSize: 12, padding: 16 }}>
          Your browser does not support this video format.{' '}
          <a href={url} download={name} style={{ color: '#8997ff' }}>
            Download the video
          </a>{' '}
          to watch it locally.
        </p>
      </video>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Image viewer
// ---------------------------------------------------------------------------
function ImageViewer({ url, name }: { url: string; name: string }) {
  return (
    <div className="card" style={{ padding: 16 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}
      >
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>🖼 {name}</span>
        <a
          href={url}
          download={name}
          className="btn"
          style={{ fontSize: 10, padding: '5px 10px' }}
        >
          ↓ Download
        </a>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={url}
        alt={name}
        style={{
          maxWidth: '100%',
          borderRadius: 8,
          border: '1px solid var(--line-soft)',
        }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// JSON viewer — fetches content then renders formatted
// ---------------------------------------------------------------------------
function JsonViewer({ url, name }: { url: string; name: string }) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [loaded, setLoaded] = useState(false)

  function load() {
    if (loaded) return
    setLoaded(true)
    fetch(url)
      .then((r) => r.text())
      .then((text) => {
        try {
          setContent(JSON.stringify(JSON.parse(text), null, 2))
        } catch {
          setContent(text)
        }
      })
      .catch((e) => setError(String(e)))
  }

  // Auto-load on mount
  if (!loaded) load()

  function copy() {
    if (!content) return
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>{ } {name}</span>
        <div style={{ display: 'flex', gap: 8 }}>
          {content && (
            <button
              className="btn"
              style={{ fontSize: 10, padding: '5px 10px' }}
              onClick={copy}
            >
              {copied ? '✓ Copied' : 'Copy'}
            </button>
          )}
          <a
            href={url}
            download={name}
            className="btn"
            style={{ fontSize: 10, padding: '5px 10px' }}
          >
            ↓ Download
          </a>
        </div>
      </div>
      {error && (
        <div className="notice error" style={{ margin: 16 }}>
          Failed to load: {error}
        </div>
      )}
      {!content && !error && (
        <div style={{ padding: 24, color: 'var(--muted)', fontSize: 12 }}>Loading…</div>
      )}
      {content && (
        <pre
          style={{
            margin: 0,
            padding: 16,
            background: '#080e18',
            color: '#9eabc0',
            fontSize: 11,
            lineHeight: 1.6,
            overflowX: 'auto',
            maxHeight: 640,
          }}
        >
          {content}
        </pre>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Text viewer — fetches and displays raw text
// ---------------------------------------------------------------------------
function TextViewer({ url, name }: { url: string; name: string }) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  function load() {
    if (loaded) return
    setLoaded(true)
    fetch(url)
      .then((r) => r.text())
      .then(setContent)
      .catch((e) => setError(String(e)))
  }

  if (!loaded) load()

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid var(--line-soft)',
        }}
      >
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>📝 {name}</span>
        <a
          href={url}
          download={name}
          className="btn"
          style={{ fontSize: 10, padding: '5px 10px' }}
        >
          ↓ Download
        </a>
      </div>
      {error && (
        <div className="notice error" style={{ margin: 16 }}>
          Failed to load: {error}
        </div>
      )}
      {!content && !error && (
        <div style={{ padding: 24, color: 'var(--muted)', fontSize: 12 }}>Loading…</div>
      )}
      {content && (
        <pre
          style={{
            margin: 0,
            padding: 16,
            background: '#080e18',
            color: '#9eabc0',
            fontSize: 11,
            lineHeight: 1.6,
            overflowX: 'auto',
            maxHeight: 480,
            whiteSpace: 'pre-wrap',
          }}
        >
          {content}
        </pre>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Fallback — download card for unknown/binary types
// ---------------------------------------------------------------------------
function DownloadCard({ artifact }: { artifact: ArtifactMeta }) {
  return (
    <div className="card" style={{ padding: 24, textAlign: 'center' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>📁</div>
      <strong style={{ display: 'block', marginBottom: 6 }}>{artifact.name}</strong>
      <p style={{ color: 'var(--muted)', fontSize: 12, marginBottom: 16 }}>
        {artifact.content_type} · {Math.ceil(artifact.size_bytes / 1024)} KB
      </p>
      <p style={{ color: 'var(--muted)', fontSize: 11, marginBottom: 20 }}>
        Preview is not available for this file type.
      </p>
      <a
        href={artifact.signed_url}
        download={artifact.name}
        className="btn btn-primary"
        target="_blank"
        rel="noreferrer"
      >
        ↓ Download file
      </a>
    </div>
  )
}
