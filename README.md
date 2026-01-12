# Railway Skills

Agent skills for [Railway](https://railway.com), following the [Agent Skills](https://agentskills.io) open format.

## Installation

```bash
curl -fsSL railway.com/skills.sh | bash
```

Supports Claude Code, OpenAI Codex, OpenCode, and Cursor. Re-run to update.

### Manual Installation

<details>
<summary>Claude Code (plugin)</summary>

```bash
claude plugin marketplace add railwayapp/railway-skills
claude plugin install railway@railway-skills
```

Update with:
```bash
claude plugin marketplace update
claude plugin update railway@railway-skills
```
</details>

<details>
<summary>Local skills copy (any agent)</summary>

Copy `plugins/railway/skills/` to your agent's skills directory:
- Claude: `~/.claude/skills/`
- Codex: `~/.codex/skills/`
- OpenCode: `~/.config/opencode/skill/`
- Cursor: `~/.cursor/skills/`
</details>

## Available Skills

| Skill | Description |
|-------|-------------|
| [status](plugins/railway/skills/status/SKILL.md) | Check Railway project status |
| [projects](plugins/railway/skills/projects/SKILL.md) | List, switch, and configure projects |
| [new](plugins/railway/skills/new/SKILL.md) | Create projects, services, databases |
| [service](plugins/railway/skills/service/SKILL.md) | Manage existing services |
| [deploy](plugins/railway/skills/deploy/SKILL.md) | Deploy local code |
| [domain](plugins/railway/skills/domain/SKILL.md) | Manage service domains |
| [environment](plugins/railway/skills/environment/SKILL.md) | Manage config (vars, commands, replicas) |
| [deployment](plugins/railway/skills/deployment/SKILL.md) | Manage deployments (list, logs, redeploy, remove) |
| [database](plugins/railway/skills/database/SKILL.md) | Add Railway databases |
| [templates](plugins/railway/skills/templates/SKILL.md) | Deploy from marketplace |
| [metrics](plugins/railway/skills/metrics/SKILL.md) | Query resource usage |
| [railway-docs](plugins/railway/skills/railway-docs/SKILL.md) | Fetch up-to-date Railway documentation |

## Hooks

This plugin includes a PreToolUse hook that auto-approves `railway-api.sh` calls to avoid permission prompts on every GraphQL API request.

## Repository Structure

```
railway-skills/
├── plugins/railway/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── hooks/
│   └── skills/
│       ├── _shared/           # Canonical shared files
│       │   ├── scripts/
│       │   └── references/
│       └── {skill-name}/
│           ├── SKILL.md
│           ├── scripts/       # Copied from _shared
│           └── references/    # Copied from _shared
├── scripts/
│   ├── install.sh             # Universal installer
│   └── sync-shared.sh         # Sync shared files
└── README.md
```

## Creating New Skills

Create `plugins/railway/skills/{name}/SKILL.md`:

```yaml
---
name: my-skill
description: What this skill does and when to use it
---

# Instructions

Step-by-step guidance for the agent.

## Examples

Concrete examples showing expected input/output.
```

## Development

### Shared Files

Scripts (`railway-api.sh`) and references (`variables.md`, etc.) are shared across skills.
Canonical versions live in `plugins/railway/skills/_shared/`.

After editing files in `_shared/`, run:
```bash
./scripts/sync-shared.sh
```

This copies shared files to each skill. Do not edit copies in individual skills directly.

## References

- [Agent Skills Specification](https://agentskills.io/specification)
- [Railway Docs](https://docs.railway.com)

## License

MIT
