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

## GraphQL Helper

```bash
~/.codex/skills/railway/lib/railway-api.sh '<query>' '<variables-json>'
```

## Safety

- Never print secrets (avoid showing `~/.railway/config.json`).
- Prefer `--json` for CLI output when available.

## References

See `references/` for task-specific flows, examples, and error handling.
