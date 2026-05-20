# Deployment Guide

## Docker Compose

Run `docker compose up` to start:

- `agentprobe` (FastAPI on port 8000)
- `postgres` (PostgreSQL 16)
- `chromadb` (vector store on port 8100 mapped from container 8000)
- `dashboard` (React UI on port 3000)

## Environment variables

Required for LLM-backed planning:

- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
- Optional: `AGENTPROBE_USE_OLLAMA=true` for local Ollama

## Health checks

The `/health` endpoint returns `{"status": "ok"}` when the API process is ready.
Downstream probes should wait until health succeeds before registering targets.

## Resource requirements

Minimum recommended resources per environment:

| Environment | CPU | Memory | Disk |
|-------------|-----|--------|------|
| Dev | 2 cores | 4 GB | 10 GB |
| Staging | 4 cores | 8 GB | 50 GB |
| Production | 8 cores | 16 GB | 200 GB |

## Logging

Set `AGENTPROBE_LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING`, or `ERROR`.
Logs are structured JSON in production.
