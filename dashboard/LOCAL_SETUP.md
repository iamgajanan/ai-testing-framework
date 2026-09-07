# Dashboard local setup

Copy `.env.local.example` to `.env.local` and provide your Supabase URL and publishable key.

```bash
cd dashboard
cp .env.local.example .env.local
npm install
npm run dev
```

Run the FastAPI SaaS API separately. The dashboard automatically tries `http://127.0.0.1:8000` and then `http://127.0.0.1:8001` for local development. In a deployed environment set `AI_TESTING_API_URL` to the reachable FastAPI service URL.
