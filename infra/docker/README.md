# Optional Docker (PostgreSQL)

Локальная разработка **не требует** Docker. По умолчанию используется SQLite (`docs/LOCAL_DEV_NO_DOCKER.md`).

PostgreSQL через Docker — для production-like проверок:

```powershell
cd infra/docker
docker compose up -d postgres
```

В корне проекта:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://mplms:mplms@localhost:5432/mplms"
uv run alembic upgrade head
```
