# Railway Claude Plugin

Claude plugin for [Railway](https://railway.com). Interact with Railway through one orchestration skill.

## Skill model

This plugin ships one Railway skill:

- `plugins/railway/skills/use-railway/SKILL.md`

`use-railway` is route-first. Routing rules and intent mapping live in `SKILL.md`.

## Reference loading pattern

1. Read `plugins/railway/skills/use-railway/SKILL.md`.
2. Choose the minimum reference set needed for the request.
3. For multi-step requests, load multiple references and compose one response.

References:

| Intent | Reference | Use for |
|---|---|---|
| Create or connect resources | `references/setup.md` | Projects, services, databases, buckets, templates, workspaces |
| Ship code or manage releases | `references/deploy.md` | Deploy, redeploy, restart, build config, monorepo, Dockerfile |
| Change configuration | `references/configure.md` | Environments, variables, config patches, domains, networking |
| Check health or debug failures | `references/operate.md` | Status, logs, metrics, build/runtime triage, recovery |
| Analyze databases | `references/analyze-db.md` | Database introspection and performance analysis — directs to DB-specific ref |
| Request from API, docs, or community | `references/request.md` | GraphQL mutations, metrics queries, Central Station, official docs |

## Architecture

### Tool routing

Choose the Railway operation path that matches the job.

- Remote MCP (`https://mcp.railway.com`): account/project/service discovery, deployment status, bounded logs, simple redeploys, simple project creation, and complex workflows through `railway-agent`. Remote MCP uses Railway OAuth and does not depend on local CLI state.
- Local CLI MCP (`railway mcp`): CLI-backed platform operations such as variables, domains, service config, templates, metrics, HTTP summaries, buckets, volumes, docs, or deploy-from-directory.
- Railway CLI (`railway`): local-machine workflows such as current-directory deploys, `railway up`, `railway run`, SSH, database analysis scripts, local linking, interactive setup, and exact command output.
- GraphQL: operations that neither MCP nor CLI exposes.

### Railway CLI

Use Railway CLI for context-aware local operations.

- Command: `railway`
- Prefer `--json` output where available.

### GraphQL API

Use GraphQL for operations the CLI doesn't expose.

- Endpoint: `https://backboard.railway.com/graphql/v2`
- API helper: `plugins/railway/skills/use-railway/scripts/railway-api.sh`

### API token

Token location: `~/.railway/config.json` under `user.token`.

Example:

```bash
# From plugins/railway/skills/use-railway
scripts/railway-api.sh \
  'query getEnv($id: String!) { environment(id: $id) { name } }' \
  '{"id": "env-uuid"}'
```

API docs: https://docs.railway.com/api/llms-docs.md

## Authoring guidance

When editing this plugin:

- Keep `SKILL.md` focused on routing, preflight, composition, and common operations.
- Keep references organized by information type (setup, deploy, configure, operate, api).
- Keep references action-oriented with reasoning. Explain why, not only what.
- Keep CLI behavior claims aligned with Railway docs and CLI source.
- Keep a single "Validated against" block at the end of each reference.
- Bump `version` in `plugins/railway/.claude-plugin/plugin.json` in any PR that changes skill content. Claude Code uses this version to detect updates — without a bump, users will not receive changes.

## References

- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins
- https://agentskills.io/specification
- https://docs.railway.com/ai/remote-mcp-server
