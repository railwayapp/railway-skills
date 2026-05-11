# Railway Skills

Agent skills and plugin packages for [Railway](https://railway.com), following the [Agent Skills](https://agentskills.io) format.

## Installation

This repository packages Railway as a plugin for Claude Code, OpenAI Codex,
and Cursor. The plugin includes the `use-railway` skill and local MCP
configuration that runs `railway mcp`.

Install the Railway CLI before using the plugin MCP server.

### Railway agent setup

To configure Railway agent support through the Railway CLI, run:

```bash
railway setup agent -y
```

This installs Railway skills, configures the Railway MCP server where
supported, and checks Railway authentication for detected tools. If you are not
authenticated, run:

```bash
railway login
```

You can also install the Railway CLI and configure agent support in one step:

```bash
bash <(curl -fsSL cli.new) --agents -y
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

## License

MIT
