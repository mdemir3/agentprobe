# AgentProbe API Platform — Technical Documentation

## Overview

The AgentProbe API is a REST service for registering target agents, generating test plans,
executing probe runs, and retrieving quality reports. The service runs on port **8000** by default.

## Authentication

All production requests require a bearer token in the `Authorization` header.
Development mode allows unauthenticated access on `localhost` only.

## Rate limits

- **Free tier:** 60 requests per minute per API key.
- **Pro tier:** 600 requests per minute.
- **Enterprise:** custom limits negotiated in contract.

Burst traffic above the limit receives HTTP **429** with a `Retry-After` header.

## Core endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/targets/` | Register a target agent |
| POST | `/plans/` | Generate a test plan |
| POST | `/runs/` | Execute a test run |
| POST | `/reports/{run_id}` | Evaluate and return a quality report |

## Probe execution

Test runs execute asynchronously with a default concurrency of **10** parallel cases.
Each case records latency in milliseconds, tool calls, and token usage when reported by the target.

## RAG / ChromaDB

Ground-truth documents are ingested per `target_id` into ChromaDB collections.
Local development uses on-disk storage at `.chromadb` unless `AGENTPROBE_CHROMA_USE_HTTP=true`.

## Error handling

- **400** — invalid payload or missing `target_id`
- **404** — unknown plan or run
- **500** — internal evaluation failure (retry with backoff)

## Versioning

The public API follows semantic versioning. Breaking changes ship only in major releases.
Current stable version: **0.1.0**.
