# Cloud Execution Worker

Phase 1A Step 5 adds an isolated execution boundary around the existing test engine.

## Local worker

The existing worker command remains compatible:

```bash
ai-test-worker --once
ai-test-worker --poll-seconds 2
```

Set `EXECUTION_TIMEOUT_SECONDS` to control the hard wall-clock limit for one SaaS execution. The default is 900 seconds.

## Container worker

Copy `.env.worker.example` to `.env.worker` and provide the server-only Supabase credentials. Never expose `SUPABASE_SERVICE_ROLE_KEY` to a browser or public client.

Build and run:

```bash
docker compose -f docker-compose.worker.yml up --build -d
```

The container runs as a non-root user and is configured with CPU, memory and PID limits. Each queued execution is additionally launched in a killable child process so a timeout does not leave the worker's main process blocked.

## Compatibility

The existing `ai-test` CLI and `LocalEngineAdapter` are unchanged. Only the SaaS `ai-test-worker` execution path uses the isolated runner. Reports are still written to the execution output directory and the existing artifact uploader persists them to private Supabase Storage.

## Deployment notes

- Give the worker only the Supabase service-role credential it needs.
- Keep the Storage bucket private.
- Set container CPU/memory limits appropriate to the browser workload.
- Use a separate worker deployment from the API service.
- Scale worker replicas horizontally; the existing queue claim operation is atomic, so a queued execution is claimed by one worker at a time.
