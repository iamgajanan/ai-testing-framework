# AI Testing Dashboard

## Local development

1. Copy `.env.local.example` to `.env.local`.
2. Set the Supabase URL and publishable key from your Supabase project.
3. Start the FastAPI SaaS API on port `8000` (the dashboard also falls back to `8001` locally).
4. Start the dashboard with `npm run dev`.

Example:

```bash
cd dashboard
cp .env.local.example .env.local
npm install
npm run dev
```

The dashboard uses the authenticated Supabase session to call the FastAPI API. `AI_TESTING_API_URL` is the production configuration point for the API; local development automatically tries `127.0.0.1:8000` and then `127.0.0.1:8001` if the configured endpoint is unavailable.

Never commit `.env.local` or service-role/secret credentials.
