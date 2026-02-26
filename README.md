# Railway Skills

Agent skill for [Railway](https://railway.com), following the [Agent Skills](https://agentskills.io) format.

## Installation

```bash
curl -fsSL railway.com/skills.sh | bash
```

You can also install via [skills.sh](https://skills.sh):

```bash
npx skills add railwayapp/railway-skills
```

Supports Claude Code, OpenAI Codex, OpenCode, and Cursor. Run the installer again to update.

## Skill surface

This repo ships one installable skill:

- [`use-railway`](plugins/railway/skills/use-railway/SKILL.md)

`use-railway` is route-first. Intent routing is defined in `SKILL.md`, and execution details are split into action-oriented references.

## Workflow coverage

`use-railway` covers:

- Project and service setup
- Deploy and release operations
- Troubleshooting and recovery
- Environment config and variables
- Networking and domains
- Status and observability
- Projects and workspaces
- Docs and community search

## Repository structure

```text
railway-skills/
├── plugins/railway/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── hooks/
│   └── skills/
│       └── use-railway/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── railway-api.sh
│           └── references/
│               ├── setup.md
│               ├── deploy.md
│               ├── configure.md
│               ├── operate.md
│               └── request.md
├── scripts/
│   └── install.sh
├── AGENTS.md
├── CLAUDE.md -> AGENTS.md
└── rfc.md
```

## Development notes

- Keep `SKILL.md` concise and routing-focused.
- Keep workflow behavior in action-oriented references.
- Keep deep schema and reference material separate from runbooks.
- Prefer canonical CLI syntax in examples.
- Keep API requests in `scripts/railway-api.sh` for consistent auth handling.

## References

- [Agent Skills Specification](https://agentskills.io/specification)
- [Railway Docs](https://docs.railway.com)

## License

MIT
