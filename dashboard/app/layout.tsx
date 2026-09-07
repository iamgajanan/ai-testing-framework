import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Universal AI Testing Framework',
  description: 'AI-powered web testing, automation, and autonomous QA platform.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>
}
