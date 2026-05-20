# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

Security fixes are applied to the latest `0.1.x` release on the default branch.

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security issue in AgentProbe, report it privately so we can
assess and address it before public disclosure.

### How to report

1. Email **hikmetdemir2424@gmail.com** with the subject line:
   `[AgentProbe Security] <short summary>`
2. Include as much detail as possible:
   - Description of the vulnerability and impact
   - Steps to reproduce
   - Affected components (API, CLI, MCP server, dashboard, Docker, n8n workflows, etc.)
   - Your environment (version, OS, configuration) if relevant
   - Proof of concept or logs, if available (redact secrets)

### What to expect

- **Acknowledgment** within 5 business days
- **Status update** as investigation progresses
- **Coordinated disclosure** — we will work with you on timing and credit (if desired) once a fix is ready

We appreciate responsible disclosure and will not pursue legal action against
researchers who report issues in good faith and allow reasonable time to remediate.

## Security considerations for deployments

AgentProbe connects to external LLM providers and target agents. When deploying:

- Keep API keys and bearer tokens in `.env` or a secrets manager; never commit them
- Restrict network access to the FastAPI API, MCP server, and dashboard in production
- Treat target agent URLs and ingested documents as sensitive input
- Run ChromaDB and PostgreSQL with appropriate authentication when exposed beyond localhost
- Review n8n workflow URLs and webhooks so they are not publicly reachable without authentication

## Dependencies

Report dependency vulnerabilities through the same private channel. We track
updates to Python (`pyproject.toml`) and Node (`dashboard/package.json`) packages
as part of regular maintenance.
