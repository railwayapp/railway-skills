# Railway Agent Plugins

Agent plugins for [Railway](https://railway.com). Interact with Railway through one orchestration skill and the Railway MCP server.

## Plugin model

The shared plugin payload lives in `plugins/railway`.

- Claude Code: `plugins/railway/.claude-plugin/plugin.json`, `plugins/railway/.mcp.json`, and the repo marketplace at `.claude-plugin/marketplace.json`.
- OpenAI Codex: `plugins/railway/.codex-plugin/plugin.json`, `plugins/railway/.mcp.json`, and the repo marketplace at `.agents/plugins/marketplace.json`.
- Cursor: `plugins/railway/.cursor-plugin/plugin.json`, `plugins/railway/.cursor-plugin/mcp.json`, and the repo marketplace at `.cursor-plugin/marketplace.json`.

Claude Code also uses `plugins/railway/hooks/hooks.json` for the existing Railway CLI/API auto-approval hook.

## Skill model

The plugin ships one Railway skill:

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
| Analyze databases | `references/analyze-db.md` | Database introspection and performance analysis, then DB-specific refs |
| Request from API, docs, or community | `references/request.md` | GraphQL mutations, metrics queries, Central Station, official docs |

## Architecture

### CLI first

Use Railway CLI for context-aware operations.

- Command: `railway`
- Prefer `--json` output where available.
- Skill telemetry: prefix Railway CLI invocations with `RAILWAY_CALLER=skill:use-railway@<plugin-version>` and a stable `RAILWAY_AGENT_SESSION`; do not run separate telemetry-only `export` commands.

### MCP

Railway CLI exposes a local MCP server with `railway mcp`.

- Keep `plugins/railway/.mcp.json` and `plugins/railway/.cursor-plugin/mcp.json` in sync.
- The local MCP config must run `railway mcp`.
- Do not store credentials in plugin MCP config. Railway CLI authentication comes from the user's local Railway login.

### GraphQL API

Use GraphQL for operations the CLI doesn't expose.

- Endpoint: `https://backboard.railway.com/graphql/v2`
- API helper: `plugins/railway/skills/use-railway/scripts/railway-api.sh`
- The API helper attaches `X-Railway-Skill-Id`, `X-Railway-Skill-Version`, and `X-Railway-Agent-Session` headers.

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
- Keep plugin versions aligned across Claude Code, Codex, and Cursor manifests when plugin behavior changes.
- Bump `version` in `plugins/railway/.claude-plugin/plugin.json` in any PR that changes skill content or published plugin behavior. Claude Code uses this version to detect updates, and users will not receive changes without a bump.

## References

- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins
- https://agentskills.io/specification
