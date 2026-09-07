'use client'

import { useFormStatus } from 'react-dom'

export function UploadSubmit() {
  const { pending } = useFormStatus()
  return (
    <button className="btn btn-primary upload-submit" type="submit" disabled={pending}>
      {pending ? 'Uploading…' : 'Upload & version'} <span>{pending ? '⏳' : '→'}</span>
    </button>
  )
}
