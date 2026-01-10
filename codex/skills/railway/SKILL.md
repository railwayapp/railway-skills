---
name: railway
description: Use for any Railway task (status, projects, deploys, domains, env vars, metrics, templates, docs).
---

# Railway (Codex)

## When to Use

- Any Railway CLI or GraphQL operation
- Project/service status, deploys, domains, variables, metrics, templates
- Railway documentation lookups

## Preflight (CLI)

```bash
command -v railway
railway whoami --json
railway status --json
```

## Preference (CLI First)

- Use the Railway CLI for all operations when available (you are authenticated locally).
- Use GraphQL only when the CLI lacks the operation or for bulk queries.

## GraphQL Helper

```bash
~/.codex/skills/railway/lib/railway-api.sh '<query>' '<variables-json>'
```

## Safety

- Never print secrets (avoid showing `~/.railway/config.json`).
- Prefer `--json` for CLI output when available.

## References

CLI flows (default):

- `references/cli/status/`
- `references/cli/projects/`
- `references/cli/new/`
- `references/cli/service/`
- `references/cli/deploy/`
- `references/cli/domain/`
- `references/cli/environment/`
- `references/cli/deployment/`
- `references/cli/database/`
- `references/cli/templates/`
- `references/cli/metrics/`
- `references/cli/reference/`

GraphQL helper + docs:

- `references/graphql/README.md`
- `references/graphql/railway-docs/`
