# Session handoff

Branch: `cursor/local-auth-and-chat-db`

`services/.env` stays on this machine and is ignored by Git. Do not commit it, `services/.venv/`, Qdrant storage, or the `.qdrant-initialized` marker files.

## Finished

- Support chat keeps provider embeddings in `trackflow_knowledge_provider` and leaves the local `trackflow_knowledge` index in place. Retrieval reuses one Qdrant client; the retrieval tests reset that client so each case stays isolated.
- A negated delivery guarantee is no longer treated as an affirmative promise. An affirmative guarantee is still refused.
- The knowledge chat accepts a valid token before the Postgres lookup, labels a closed socket as not connected, and clears an expired token.
- Database connections are pooled, and chat token text is queued instead of written once per delta.
- Reporting distinguishes a pipeline that has never run from a completed run with zero valid KPI rows. The recorded run for 14–21 September 2026 completed with 0 rows because both source events include a warehouse and neither includes `client_id`.
- Incident Analysis sends the signed-in bearer token. The page loads. Every counter is zero because `services/data/db.json` has no incident documents.
- The older incident file `scripts/incidents-trackflow.csv` has 100 rows: 95 valid and 5 invalid. It was not copied into TinyDB. Postgres has no incidents table. The repo-root `data/db.json` is empty.
- The weekly report task ran once on the local Celery worker and shows as Succeeded in Flower. It did not change inventory or telemetry and did not send email.

## Still pending

- Seed incidents only when a copy from `scripts/incidents-trackflow.csv` into TinyDB is explicitly requested.
- Docker is not installed here. Redis, Qdrant, the Celery worker, and Flower are local processes, not Compose containers.
- Backoffice pages still require the existing local sign-in. Do not reset that password.

## Restart tomorrow

Leave any process that is already listening. Open a separate PowerShell window for each long-running process, starting from the repository root:

```powershell
# Public website, port 3001
npm.cmd run dev --prefix uis\website -- --port 3001

# Backoffice, port 3000
npm.cmd run dev --prefix uis\backoffice -- --port 3000

# API, port 8000. Working directory: services. Loads .env without printing it.
Set-Location services
$env:PYTHONUNBUFFERED = "1"
@'
from dotenv import load_dotenv
import uvicorn
load_dotenv(".env", override=True)
uvicorn.run("main:app", host="127.0.0.1", port=8000)
'@ | & .\.venv\Scripts\python.exe -

# Qdrant, port 6333
$env:QDRANT__STORAGE__STORAGE_PATH = Join-Path $env:TEMP "qdrant-v1.19.2\storage"
& "$env:LOCALAPPDATA\Temp\qdrant-v1.19.2\qdrant.exe"

# Redis, port 6379. Start this before the worker and Flower.
& "$env:LOCALAPPDATA\Temp\redis-win\redis-server.exe" --bind 127.0.0.1 --port 6379 --maxmemory-policy noeviction --protected-mode yes

# Celery worker. Prefork cannot run on this Windows host.
# Working directory: services.
Set-Location services
& .\.venv\Scripts\celery.exe -A celery_app worker --loglevel=info --pool=solo

# Flower, http://127.0.0.1:5555. Working directory: services.
Set-Location services
$env:FLOWER_UNAUTHENTICATED_API = "true"
& .\.venv\Scripts\celery.exe -A celery_app flower --address=127.0.0.1 --port=5555
```
