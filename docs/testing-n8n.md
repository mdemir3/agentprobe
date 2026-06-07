# Testing n8n AI Workflows

AgentProbe ships ready-to-import n8n workflows in
[`integrations/n8n/`](../integrations/n8n/) so you can run probes on a schedule
or as a deploy gate, and alert on regressions.

## Included workflows

| File | What it does |
|------|--------------|
| `n8n_scheduled_quality.json` | Runs a probe on a cron schedule and posts the quality score to Slack. |
| `n8n_deploy_gate.json` | Runs a probe in a deployment pipeline and blocks/continues based on the overall score. |

## Import

1. In n8n: **Workflows → Import from File**.
2. Select a JSON file from `integrations/n8n/`.
3. Set credentials/URLs for the nodes (your AgentProbe API or MCP server URL,
   Slack webhook, target agent URL).
4. Activate the workflow.

## How it drives AgentProbe

The workflows call AgentProbe through one of two surfaces:

- **MCP server** (`mcp_server/server.py`) — exposes `probe_connect`,
  `probe_generate_plan`, `probe_run`, and `probe_evaluate` as MCP tools.
- **REST API** (`POST /targets`, `POST /plans`, `POST /runs`,
  `GET /reports/{id}`).

A deploy gate typically: registers the target → generates a plan → runs it →
fetches the report → compares `overall_score` to a threshold → fails the step (or
sends a Slack alert) when it drops below the bar.

## Probing an n8n AI workflow as the *target*

You can also test an n8n AI workflow itself: expose it via an n8n **Webhook**
node that accepts `{ "message": "..." }` and returns
`{ "response": "...", "tool_calls": [], "usage": {} }`, then:

```bash
agentprobe probe https://your-n8n-host/webhook/agent --type api --tests 20
```
