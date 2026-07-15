# Backend

This backend foundation now provides:

- a FastAPI application entrypoint;
- router registration;
- `GET /health` and `GET /health/database`;
- environment-based configuration through one settings object;
- PostgreSQL connection settings and SQLAlchemy session management;
- Alembic migration support for the operational schema;
- operational SQLAlchemy models for the documented PostgreSQL tables.

Local setup:

```bash
cp .env.example .env
cd backend
alembic upgrade head
pytest
```

Docker-based local setup:

```bash
docker compose up -d postgres
docker compose ps
cd backend
alembic upgrade head
```

This phase intentionally does not implement deterministic seed data, ontology loading, functions, actions, permissions, audit workflows, MCP tools, or assistant behavior.
