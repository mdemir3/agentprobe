# Quick Start

This guide takes you from a fresh clone to a quality report in a few minutes.
No cloud API keys are required — you can run everything locally against the
bundled dummy agent or a local Ollama model.

## 1. Install

AgentProbe targets **Python 3.11+**.

```bash
git clone https://github.com/mdemir3/agentprobe.git
cd agentprobe
pip install -e ".[dev]"
```

Verify the CLI is available:

```bash
agentprobe version
```

The CLI exposes three commands: `connect`, `probe`, and `version`.

## 2. Probe the bundled dummy agent (zero setup)

The repo ships a small FastAPI "agent" you can probe immediately.

```bash
# Terminal 1 — start the dummy agent
python examples/dummy_tool_agent/app.py

# Terminal 2 — discover its tools, then probe it end-to-end
agentprobe connect http://localhost:8001 --type api --name "Dummy Agent"
agentprobe probe   http://localhost:8001 --type api --tests 20 -o report.json
```

`probe` generates a test plan, runs every case, evaluates the results, and prints
a graded quality report. With `-o report.json` it also writes the full report
(including confidence intervals) to disk.

## 3. Probe a local Ollama model (zero API cost)

```bash
# Terminal 1 — pull and serve a model
ollama run llama3.1

# Terminal 2 — probe it, running each test 3× for variance
agentprobe probe http://localhost:11434 --type rest \
  --model llama3.1 --tests 50 --runs 3 -o report.json
```

`--runs 3` executes each test case three times (seeds `seed`, `seed+1`,
`seed+2`). The report shows **mean ± std** and a **95% confidence interval** per
metric instead of a single point estimate.

## 4. Read the report

The console prints an at-a-glance scorecard:

```
Overall Score: 92.7% (Grade: A)
Tests: 50 passed / 0 failed / 0 errors
Hallucination Rate: 20.0%
Tool Accuracy: 100.0%
Safety Pass Rate: 100.0%
Avg Latency: 2ms
```

The JSON file adds per-metric statistics in the shape:

```json
{
  "overall_score": { "mean": 0.927, "std": 0.03, "ci_low": 0.91, "ci_high": 0.94, "method": "t", "n": 50 },
  "hallucination_rate": { "mean": 0.2, "ci_low": 0.12, "ci_high": 0.31, "method": "wilson", "n": 50 }
}
```

Rate metrics use a **Wilson score interval**; continuous metrics use a
**t-distribution** (df = n − 1). See
[Writing Custom Eval Scorers](custom-scorers.md) for how the scores are produced.

## 5. (Optional) Run the full platform

To use the REST API and React dashboard for the granular
discover → plan → run → evaluate flow and run history:

```bash
docker compose up
```

- API: http://localhost:8000 (`/docs` for the OpenAPI UI)
- Dashboard: http://localhost:5173

## Next steps

- [Testing LangChain Agents](testing-langchain.md)
- [Testing CrewAI Crews](testing-crewai.md)
- [Testing n8n AI Workflows](testing-n8n.md)
- [Enabling hallucination detection](../src/INTEGRATION_GUIDE.md)
- [CI/CD Integration](ci-cd-integration.md)
