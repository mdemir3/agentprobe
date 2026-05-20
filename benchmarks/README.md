# AgentProbe Benchmarks

Public, reproducible benchmarks comparing **five agent stacks** against **three RAG corpora** using the AgentProbe evaluation pipeline (FastAPI · LangGraph · ChromaDB · DeepEval).

## Matrix

| | Technical docs | Policy / legal | Product FAQ |
|---|----------------|----------------|-------------|
| **LangChain ReAct** | ✓ | ✓ | ✓ |
| **CrewAI demo** | ✓ | ✓ | ✓ |
| **OpenAI Assistants** | ✓ | ✓ | ✓ |
| **AutoGen** | ✓ | ✓ | ✓ |
| **Basic MCP server** | ✓ | ✓ | ✓ |

**15 probe runs** per full benchmark (5 × 3).

## Methodology

### 1. Agent wrappers (`benchmarks/agents/`)

Each file is a **FastAPI shim** that emulates the *behavioral profile* of a public stack (latency, tool-call reliability, hallucination tendency) while exposing the REST contract AgentProbe uses in production:

- `GET /health`
- `GET /tools`
- `POST /chat` → `{ "response", "tool_calls", "usage" }`

Wrappers are **not** full LangChain/CrewAI installs — they are deterministic, offline-friendly stand-ins so benchmarks run in CI without external API keys. Profiles are tuned per framework based on typical failure modes observed in agent QA.

| Agent | Port | Hallucination bias | Tool miss rate | Latency (base) |
|-------|------|-------------------|----------------|----------------|
| LangChain ReAct | 8101 | 10% | 8% | 140 ms |
| CrewAI demo | 8102 | 18% | 12% | 220 ms |
| OpenAI Assistants | 8103 | 7% | 5% | 280 ms |
| AutoGen | 8104 | 22% | 15% | 190 ms |
| MCP server | 8105 | 5% | 3% | 110 ms |

### 2. RAG corpora (`benchmarks/datasets/`)

| Corpus | Contents | Files |
|--------|----------|-------|
| `technical_docs` | API platform & deployment docs | `api_platform.md`, `deployment.md` |
| `policy_legal` | Privacy policy & terms of service | `privacy_policy.md`, `terms_of_service.md` |
| `product_faq` | Shipping, returns, catalog | `shipping_returns.md`, `product_catalog.md` |

Before each run, documents are ingested into **ChromaDB** (local `.chromadb` under `benchmarks/results/chromadb`) with `target_id = {agent_id}__{corpus_id}`.

### 3. Probe execution (`run_benchmark.py`)

For each agent × corpus cell:

1. Start the agent wrapper (uvicorn subprocess).
2. Ingest the corpus into ChromaDB.
3. **Connect & discover** tools via `APIConnector`.
4. **Generate test plan** — rule-based planner by default (no cloud API keys).
5. **Execute** all cases with `execute_test_run`.
6. **Evaluate** with `evaluate_run` (tool accuracy, safety, RAG hallucination check, latency).
7. Compute **heuristic hallucination rate** (offline keyword/overlap judge) for charting when no LLM judge is configured.

### 4. Reporting (`visualize.py`)

- `benchmarks/results/summary.json` — full run payload
- `benchmarks/results/{agent}__{corpus}.json` — per-cell detail
- `benchmarks/results/charts/*.png` — matplotlib charts
- `benchmarks/results/REPORT.md` — **LinkedIn-ready** report with tables and embedded charts

## Quick start

From the repository root (Python 3.12, AgentProbe installed):

```bash
pip install -e ".[dev]"
pip install matplotlib

python benchmarks/run_benchmark.py
```

Options:

```bash
python benchmarks/run_benchmark.py --max-cases 12      # default
python benchmarks/run_benchmark.py --skip-ingest       # reuse Chroma data
python benchmarks/visualize.py                       # regenerate charts from summary.json
```

Open **`benchmarks/results/REPORT.md`** and screenshot the charts section for social posts.

### Run a single agent locally

```bash
export BENCHMARK_CORPUS=product_faq
export BENCHMARK_CORPUS_ROOT=benchmarks/datasets/product_faq
python benchmarks/agents/langchain_react.py
```

## Metrics

| Metric | Source |
|--------|--------|
| Overall score | AgentProbe `QualityReport.overall_score` |
| Tool accuracy | AgentProbe eval pipeline |
| Hallucination (charts) | Heuristic judge avg across responses (offline); AgentProbe RAG score in JSON `report` |
| Latency | Per-probe `latency_ms` from target agent |

## Limitations

- Wrappers simulate framework behavior; swap in real LangChain/CrewAI/etc. endpoints by changing the connector URL in `run_benchmark.py`.
- LLM-based claim judging requires `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or Ollama — the default harness uses heuristic hallucination scoring for reproducible charts.
- First Chroma ingest downloads the **sentence-transformers** embedding model (~80 MB).

## Citation

If you use these benchmarks, link to [AgentProbe](https://github.com/mdemir3/agentprobe) and note the matrix version (`0.1.0`) and date in `REPORT.md`.
