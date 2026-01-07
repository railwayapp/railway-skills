# Railway Skills

Agent skills for [Railway](https://railway.com), following the [Agent Skills](https://agentskills.io) open format.

## Installation

### Claude Code (via Marketplace)

```bash
claude plugin marketplace add railwayapp/railway-claude-plugin
claude plugin install railway@railway-claude-plugin
```

### Claude Code (from local clone)

```bash
git clone git@github.com:railwayapp/railway-claude-plugin.git ~/railway-claude-plugin
claude --plugin-dir ~/railway-claude-plugin/plugins/railway
```

Skills are invoked automatically when relevant.

### Updating

```bash
claude plugin marketplace update
claude plugin update railway@railway-claude-plugin
```

Or use `/plugin` to open the interactive plugin manager.

### Other Agents

Copy `plugins/railway/skills/` to your agent's skills location, or reference the SKILL.md files directly.

## Available Skills

| Skill | Description |
|-------|-------------|
| [status](plugins/railway/skills/status/SKILL.md) | Check Railway project status |
| [new](plugins/railway/skills/new/SKILL.md) | Create projects, services, databases |
| [service](plugins/railway/skills/service/SKILL.md) | Manage existing services |
| [deploy](plugins/railway/skills/deploy/SKILL.md) | Deploy local code |
| [domain](plugins/railway/skills/domain/SKILL.md) | Manage service domains |
| [environment](plugins/railway/skills/environment/SKILL.md) | Manage config (vars, commands, replicas) |
| [deployment](plugins/railway/skills/deployment/SKILL.md) | Manage deployments (list, logs, redeploy, remove) |
| [database](plugins/railway/skills/database/SKILL.md) | Add Railway databases |
| [templates](plugins/railway/skills/templates/SKILL.md) | Deploy from marketplace |
| [metrics](plugins/railway/skills/metrics/SKILL.md) | Query resource usage |
| [update-project](plugins/railway/skills/update-project/SKILL.md) | Update project settings |

## Hooks

This plugin includes a PreToolUse hook that auto-approves `railway-api.sh` calls to avoid permission prompts on every GraphQL API request.

## Repository Structure

```
railway-claude-plugin/
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── railway/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── hooks/
│       │   ├── hooks.json
│       │   └── auto-approve-api.sh
│       └── skills/
│           ├── lib/
│           ├── reference/
│           └── {skill-name}/SKILL.md
├── AGENTS.md
├── CLAUDE.md → AGENTS.md
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

## References

- [Agent Skills Specification](https://agentskills.io/specification)
- [Railway Docs](https://docs.railway.com)

## License

MIT
