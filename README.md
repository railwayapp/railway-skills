# Railway Skills

Agent skills and plugin packages for [Railway](https://railway.com), following the [Agent Skills](https://agentskills.io) format.

## Installation

This repository packages Railway as a plugin for Claude Code, OpenAI Codex,
and Cursor. The plugin includes the `use-railway` skill and local MCP
configuration that runs `railway mcp`.

Install and authenticate the Railway CLI before using the plugin MCP server:

```bash
railway login
```

### Claude Code

Use the official Anthropic marketplace for published Claude Code releases:

```text
/plugin install railway@claude-plugins-official
```

The official marketplace pins each plugin to a specific commit. Changes in this repository become available through `claude-plugins-official` after the Railway entry in `anthropics/claude-plugins-official` is updated to a commit that contains them.

To install the version published by this repository's Claude Code marketplace,
add the marketplace and install the `railway` plugin from it:

```text
/plugin marketplace add railwayapp/railway-skills
/plugin install railway@railway-skills
/reload-plugins
```

### OpenAI Codex

Codex support in this repository is packaged through the repo-local Codex
marketplace manifest. The manifest makes the `railway` plugin available to
Codex environments that load this repository's plugin marketplace:

- Plugin manifest: [`plugins/railway/.codex-plugin/plugin.json`](plugins/railway/.codex-plugin/plugin.json)
- Marketplace: [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json)

OpenAI's public Codex guidance says plugins are managed from the Codex
**Plugins** surface. When Railway is available in your Codex plugin library,
install it there:

1. Open Codex.
2. Select **Plugins** in the top-left corner.
3. Browse the plugin library.
4. Search for Railway.
5. Install the Railway plugin.

### Cursor

When Railway is listed in the Cursor Marketplace, install it from Cursor:

1. Open the marketplace panel in Cursor.
2. Search for Railway.
3. Install the Railway plugin.

Teams and Enterprise admins can distribute Railway from this GitHub repository
as a team marketplace:

1. Open **Dashboard**.
2. Go to **Settings**.
3. Open **Plugins**.
4. In **Team Marketplaces**, click **Import**.
5. Paste the GitHub repository URL for this repository.
6. Review the parsed `railway` plugin.
7. Optional: Set Team Access groups.
8. Name and save the marketplace.
9. Install the plugin from Cursor's marketplace panel, or mark it as required
   for the appropriate distribution group.

- Plugin manifest: [`plugins/railway/.cursor-plugin/plugin.json`](plugins/railway/.cursor-plugin/plugin.json)
- Marketplace: [`.cursor-plugin/marketplace.json`](.cursor-plugin/marketplace.json)

### Skills-only install

For tools that support Agent Skills but don't support plugins, install the Railway skill:

```bash
curl -fsSL railway.com/skills.sh | bash
```

You can also install via [skills.sh](https://skills.sh):

```bash
npx skills add railwayapp/railway-skills
```

Supports Claude Code, OpenAI Codex, OpenCode, Cursor or any coding agent. Run the installer again to update.

### Railway MCP

The plugin includes local MCP config for tools that support plugin-bundled MCP servers:

- Claude Code and Codex: [`plugins/railway/.mcp.json`](plugins/railway/.mcp.json)
- Cursor: [`plugins/railway/.cursor-plugin/mcp.json`](plugins/railway/.cursor-plugin/mcp.json)

Both configs run `railway mcp`. Install and authenticate the Railway CLI before using the MCP server.

## Marketplace manifests

This repo exposes one marketplace manifest per host ecosystem. Each marketplace lists the same shared `railway` plugin in `plugins/railway`.

- Claude Code: [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)
- OpenAI Codex: [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json)
- Cursor: [`.cursor-plugin/marketplace.json`](.cursor-plugin/marketplace.json)

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
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── plugins/railway/
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── .codex-plugin/
│   │   └── plugin.json
│   ├── .cursor-plugin/
│   │   ├── mcp.json
│   │   └── plugin.json
│   ├── .mcp.json
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
├── .claude-plugin/
│   └── marketplace.json
├── .cursor-plugin/
│   └── marketplace.json
├── AGENTS.md
└── CLAUDE.md -> AGENTS.md
```

## Development notes

- Keep `SKILL.md` concise and routing-focused.
- Keep workflow behavior in action-oriented references.
- Keep deep schema and reference material separate from runbooks.
- Prefer canonical CLI syntax in examples.
- Keep API requests in `scripts/railway-api.sh` for consistent auth handling.
- Keep plugin manifests and MCP config aligned across Claude Code, Codex, and Cursor.

## References

- [Agent Skills Specification](https://agentskills.io/specification)
- [Railway Docs](https://docs.railway.com)
- [Claude Code plugin installation](https://code.claude.com/docs/en/discover-plugins)
- [Codex plugins and skills](https://openai.com/academy/codex-plugins-and-skills/)
- [Cursor plugins marketplace](https://github.com/cursor/plugins)

## License

MIT
