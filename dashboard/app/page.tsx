import Link from 'next/link'

export default function LandingPage() {
  return (
    <main>
      <header className="container nav">
        <Link className="brand" href="/"><span className="brand-mark">AI</span> Universal AI Testing</Link>
        <nav className="nav-links" aria-label="Main navigation">
          <a href="#features">Features</a><a href="#pricing">Pricing</a><Link href="/docs">Docs</Link>
        </nav>
        <div className="nav-actions">
          <Link className="btn btn-ghost" href="/login">Log in</Link>
          <Link className="btn" href="/book-demo">Book a demo</Link>
          <Link className="btn btn-primary" href="/signup">Start free trial</Link>
        </div>
      </header>

      <section className="container hero">
        <span className="eyebrow">AI-native QA platform</span>
        <h1>Ship with confidence. <span className="gradient">Test beyond scripts.</span></h1>
        <p>Automate web testing with Playwright, AI-powered locators, self-healing selectors, autonomous exploration, API validation, visual regression, and cloud execution.</p>
        <div className="hero-actions">
          <Link className="btn btn-primary" href="/signup">Start free trial →</Link>
          <Link className="btn" href="/book-demo">Book a demo</Link>
        </div>
      </section>

      <section className="section" id="features">
        <div className="container"><h2>One platform for modern QA</h2><p className="section-lead">From a local test file to isolated cloud execution, the platform keeps deterministic Playwright execution at the core while adding AI and SaaS capabilities around it.</p>
          <div className="grid">
            <Feature title="AI test generation" text="Explore live applications, discover same-origin pages, and turn observed workflows into executable suites." />
            <Feature title="Self-healing automation" text="Recover from selector changes with confidence-aware AI location and deterministic fallbacks." />
            <Feature title="Cloud execution" text="Queue project-scoped executions and run them in isolated, resource-limited workers." />
            <Feature title="Visual + API checks" text="Mock network traffic, validate browser API responses, and compare screenshots against baselines." />
            <Feature title="Artifacts & reports" text="Keep HTML, JSON, screenshots, traces, videos, diagnostics, and signed artifact downloads together." />
            <Feature title="Multi-tenant by design" text="Supabase Auth, organizations, projects, API keys, storage, and RLS keep customer data isolated." />
          </div>
        </div>
      </section>

      <section className="section" id="pricing"><div className="container"><h2>Simple pricing</h2><p className="section-lead">Start free, then scale execution when your team needs it.</p><div className="grid">
        <Plan name="Free" price="$0" text="For evaluation and small projects." items={['Local CLI testing','AI test generation','HTML + JSON reports']} />
        <Plan name="Pro" price="$49" text="For teams running continuous QA." items={['Cloud executions','Parallel workers','Private artifacts','Project API keys']} />
        <Plan name="Enterprise" price="Custom" text="For larger engineering organizations." items={['Advanced tenancy','Dedicated runners','Custom limits','Priority support']} />
      </div></div></section>

      <footer className="footer"><div className="container">Universal AI Testing Framework · Production-oriented AI testing infrastructure.</div></footer>
    </main>
  )
}

function Feature({ title, text }: { title: string; text: string }) { return <article className="card"><h3>{title}</h3><p>{text}</p></article> }
function Plan({ name, price, text, items }: { name:string; price:string; text:string; items:string[] }) { return <article className="card"><h3>{name}</h3><div className="price">{price}<small>{price !== 'Custom' && '/month'}</small></div><p>{text}</p><ul>{items.map(item=><li key={item} className="muted">{item}</li>)}</ul><Link className="btn btn-primary" href="/signup">Get started</Link></article> }
