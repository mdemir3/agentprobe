# CI/CD Integration

Use AgentProbe as an automated **quality gate**: run a probe against your agent
on every change and fail the build if quality regresses.

## The pattern

1. Start your agent (or a deployed staging URL).
2. Run `agentprobe probe ... -o report.json`.
3. Read `report.json` and compare metrics to thresholds.
4. Exit non-zero to block the pipeline when a threshold is breached.

`report.json` contains the full `QualityReport`, including `overall_score`,
`hallucination_rate`, `tool_accuracy`, `safety_pass_rate`, and a
`confidence_interval` block per metric.

## GitHub Actions example

```yaml
name: Agent Quality Gate
on: [pull_request]

jobs:
  probe:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"

      - name: Start agent
        run: |
          python examples/dummy_tool_agent/app.py &
          sleep 3

      - name: Probe
        run: agentprobe probe http://localhost:8001 --type api --tests 20 -o report.json

      - name: Enforce thresholds
        run: |
          python - <<'PY'
          import json, sys
          r = json.load(open("report.json"))
          score = r["overall_score"]
          halluc = r["hallucination_rate"]
          print(f"overall={score:.2%} hallucination={halluc:.2%}")
          if score < 0.80 or halluc > 0.20:
              sys.exit("Quality gate failed")
          PY
```

> Tip: gate on the **lower CI bound** (`confidence_interval.overall_score.ci_low`)
> rather than the point estimate to avoid passing on a lucky run.

## GitLab CI example

```yaml
agent_quality:
  image: python:3.12
  script:
    - pip install -e ".[dev]"
    - python examples/dummy_tool_agent/app.py & sleep 3
    - agentprobe probe http://localhost:8001 --type api --tests 20 -o report.json
    - |
      python -c "import json,sys; r=json.load(open('report.json')); \
        sys.exit('gate failed') if r['overall_score']<0.8 else None"
```

## n8n deploy gate

For a no-code gate with Slack alerts, import
[`integrations/n8n/n8n_deploy_gate.json`](../integrations/n8n/n8n_deploy_gate.json).
See [Testing n8n AI Workflows](testing-n8n.md).

## This repo's own CI

`.github/workflows/ci.yml` runs `ruff`, `black --check`, `mypy`, and `pytest`
with coverage on every push and PR. `.github/workflows/release.yml` builds and
publishes to PyPI on `v*` tags via trusted publishing.
