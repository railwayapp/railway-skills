# Railway Claude Plugin

Claude Code plugin for [Railway](https://railway.com). Manage your Railway projects directly from Claude Code.

## Installation

```bash
claude plugin add railwayapp/railway-claude-plugin
```

## Requirements

- [Railway CLI](https://docs.railway.com/guides/cli) installed and authenticated
- A linked Railway project (`railway link`)

## Skills

| Skill | Description |
|-------|-------------|
| `status` | Check linked project and environment |
| `service` | Create, update, and check service status |
| `deploy` | Deploy local code with `railway up` |
| `domain` | Add and manage service domains |
| `environment-config` | View environment configuration |
| `environment-update` | Update service config (variables, image, commands) |
| `environment-apply` | Apply staged changes and deploy |
| `deployment-logs` | View build and runtime logs |

## Usage

Skills are invoked automatically based on your request:

- "create a new service called api"
- "deploy this to railway"
- "add a domain to my service"
- "set the PORT variable to 8080"
- "check the deployment status"

## License

MIT
