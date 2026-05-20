# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [0.1.0] - 2026-05-20

### Added

- **AgentProbe core** — Python 3.12 package with FastAPI backend, CLI (`agentprobe`), and in-memory API store
- **Target connectors** — REST API and MCP discovery for external LLM agents
- **Probe engine** — LangGraph-oriented test planning and async test execution (`planner`, `runner`)
- **Test plan generation** — LLM-backed plans (Anthropic, OpenAI), local **Ollama**, **MCP tool bridge**, and rule-based fallback
- **Evaluation pipeline** — Quality reports with overall score, tool accuracy, safety, latency, and cost metrics (DeepEval + custom scorers)
- **RAG hallucination detection** — ChromaDB ingestion, sentence-transformers embeddings, claim extraction, and faithfulness judging against ground-truth documents
- **Example agents** — `dummy_tool_agent` (realistic tools), `bad_agent` (intentionally unreliable), and `mcp_planner_bridge` for local testing
- **MCP server** — HTTP MCP-compatible surface to trigger connect, plan, run, and evaluate from MCP clients
- **React dashboard** — Vite + React + Tailwind UI for targets, runs, and quality reports
- **Docker Compose** — AgentProbe API, PostgreSQL, ChromaDB, and dashboard services
- **n8n integrations** — Deployment quality gate and scheduled quality workflow JSON templates
- **Integration tests** — `test_full_flow.py` (end-to-end probe) and `test_hallucination.py` (RAG eval)
- **Configuration** — `.env.example` for providers, Chroma, Ollama, MCP bridge, and concurrency limits

[Unreleased]: https://github.com/mdemir3/agentprobe/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mdemir3/agentprobe/releases/tag/v0.1.0
