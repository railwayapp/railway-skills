# Railway Agent Plugins

Agent plugins for [Railway](https://railway.com). Interact with Railway through one orchestration skill and the Railway MCP server.

## Plugin model

The shared plugin payload lives in `plugins/railway`.

- Claude Code: `plugins/railway/.claude-plugin/plugin.json`, `plugins/railway/.mcp.json`, and the repo marketplace at `.claude-plugin/marketplace.json`.
- OpenAI Codex: `plugins/railway/.codex-plugin/plugin.json`, `plugins/railway/.mcp.json`, and the repo marketplace at `.agents/plugins/marketplace.json`.
- Grok Build / xAI marketplace: resolves the **repo root** as the plugin and auto-discovers components from standard root locations. The root therefore exposes `.grok-plugin/plugin.json` (metadata) plus three symlinks into the payload — `skills` → `plugins/railway/skills`, `hooks` → `plugins/railway/hooks`, `.mcp.json` → `plugins/railway/.mcp.json` — so no config is duplicated and `plugins/railway` stays the single source of truth.
- Cursor: `plugins/railway/.cursor-plugin/plugin.json`, `plugins/railway/.cursor-plugin/mcp.json`, and the repo marketplace at `.cursor-plugin/marketplace.json`.

Claude Code and Grok Build also use `plugins/railway/hooks/hooks.json` for the existing Railway CLI/API auto-approval hook. The hook command resolves `${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/auto-approve-api.sh`, which works through the root `hooks` symlink under Grok.

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
| Use a sandbox or build remotely | `references/sandbox.md` | Sandboxes: create/fork, remote exec, remote template builds, checkpoints, port forwarding (requires Priority Boarding) |
| Analyze databases | `references/analyze-db.md` | Database introspection and performance analysis, then DB-specific refs |
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
- Keep plugin versions aligned across the Claude Code, Codex, Cursor, and root Grok (`.grok-plugin/plugin.json`) manifests when plugin behavior changes.
- The root `skills`, `hooks`, and `.mcp.json` symlinks must keep pointing into `plugins/railway`; never replace them with copies, or Grok and the payload will drift.
- Bump `version` in `plugins/railway/.claude-plugin/plugin.json` in any PR that changes skill content or published plugin behavior. Claude Code uses this version to detect updates, and users will not receive changes without a bump.

## References

- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins
- https://agentskills.io/specification
- https://docs.railway.com/ai/remote-mcp-server
