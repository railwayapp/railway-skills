# Railway Skills

Agent skills and plugin packages for [Railway](https://railway.com), following the [Agent Skills](https://agentskills.io) format.

## Installation

This repository includes Railway plugin packaging for Claude Code, OpenAI
Codex, Grok Build, and Cursor. The plugin includes the `use-railway` skill and
local MCP configuration that runs `railway mcp`.

Claude Code is the currently published official plugin path. Codex and Cursor
support is packaged in this repository for environments that load this repo's
marketplace manifests or distribute the plugin from this GitHub repository.

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
bash <(curl -fsSL https://railway.com/install.sh) --agents -y
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

There is not currently an official public Codex listing for Railway. Add this
GitHub repository as a Codex marketplace:

1. Open Codex.
2. Select **Plugins** in the sidebar.
3. Open the **More** dropdown.
4. Click **Add more**.
5. Enter [`railwayapp/railway-skills`](https://github.com/railwayapp/railway-skills) as the marketplace source.

### Grok Build

Add this GitHub repository as a Grok marketplace:

```bash
grok plugin marketplace add railwayapp/railway-skills
```

Then install the `railway` plugin from Grok's TUI:

1. Run `grok`.
2. Open the extensions modal with `/plugins`.
3. Go to the **Marketplace** tab.
4. Select `railway` from the `railway-skills` marketplace.
5. Press `i` to install.

In `grok 0.2.20`, the CLI install command is source-based and does not install
the marketplace plugin by name, so use the TUI marketplace install after adding
the source.

### Cursor

There is not currently an official public Cursor listing for Railway. Add this
GitHub repository from Cursor settings:

1. Open **Settings**.
2. Select **Plugins**.
3. Paste `https://github.com/railwayapp/railway-skills` in the **Search or Paste Link** input.
4. Click the Railway plugin.
5. Click **Add to Cursor**.

- Plugin manifest: [`plugins/railway/.cursor-plugin/plugin.json`](plugins/railway/.cursor-plugin/plugin.json)
- Marketplace: [`.cursor-plugin/marketplace.json`](.cursor-plugin/marketplace.json)

### Railway MCP

The plugin includes local MCP config for tools that support plugin-bundled MCP servers:

- Claude Code, Codex, and Grok Build: [`plugins/railway/.mcp.json`](plugins/railway/.mcp.json)
- Cursor: [`plugins/railway/.cursor-plugin/mcp.json`](plugins/railway/.cursor-plugin/mcp.json)

Both configs run `railway mcp`. Install and authenticate the Railway CLI before using the MCP server.

## Marketplace manifests

This repo exposes marketplace manifests for host ecosystems that need their own
manifest shape. Each marketplace lists the same shared `railway` plugin in
`plugins/railway`. Grok Build consumes the Claude Code marketplace/plugin
compatibility path.

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
- Railway Agent, MCP, and skills setup
- Projects and workspaces
- Docs and community search

## License

MIT
