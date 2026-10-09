# Railway Skills

Agent skills for [Railway](https://railway.com), following the [Agent Skills](https://agentskills.io) format. 

This repository also includes Railway plugin packaging for ChatGPT, OpenAI Codex,
Claude Code, Grok Build, and Cursor. Each plugin package includes the
`use-railway` Agent Skill and Railway's hosted MCP server. Railway is also
available as a connector for Claude.


## Railway agent setup

To install the Railway CLI and configure agent support, run:

```bash
curl -fsSL agents.railway.com | sh
```

This installs the Railway CLI and skills, configures the Railway MCP server for
detected tools, and checks Railway authentication. If you are not authenticated,
run:

```bash
railway login
```

If the Railway CLI is already installed, configure agent support directly:

```bash
railway setup agent
```

## Installing Railway integrations

### skills.sh

Install the `use-railway` skill into any agent supported by
[skills.sh](https://skills.sh):

```bash
npx skills add railwayapp/railway-skills
```

The skill uses Railway's MCP server when it is connected and the Railway CLI
otherwise.

### ChatGPT and OpenAI Codex

Install the official [Railway plugin for ChatGPT and
Codex](https://chatgpt.com/plugins/plugin_asdk_app_6a502589384081919c5decf93496c9d1)
from the shared plugin directory. The plugin includes the `use-railway` skill
and Railway's hosted MCP server. Connect your Railway account when prompted,
then start a new chat or task to use the plugin.

To install the version published by this repository directly, add this GitHub
repository as a Codex marketplace:

1. Open Codex.
2. Select **Plugins** in the sidebar.
3. Open the **More** dropdown.
4. Click **Add more**.
5. Enter [`railwayapp/railway-skills`](https://github.com/railwayapp/railway-skills) as the marketplace source.

- Plugin manifest: [`plugins/railway/.codex-plugin/plugin.json`](plugins/railway/.codex-plugin/plugin.json)
- Marketplace: [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json)

### Claude

Add the official [Railway connector for
Claude](https://claude.ai/directory/connectors/railway) from Claude's connector
directory. The connector uses Railway's hosted MCP server and OAuth, so it
doesn't require the Railway CLI.

For terminal-based workflows with Railway's agent skill and hooks, install the
Claude Code plugin.

### Claude Code

The official Anthropic marketplace is available in Claude Code by default.
Install Railway and reload plugins:

```text
/plugin install railway@claude-plugins-official
/reload-plugins
```

You can also run `/plugin` and select the **Discover** tab to browse the
official marketplace. If Claude Code can't find Railway, refresh the marketplace
and retry the installation:

```text
/plugin marketplace update claude-plugins-official
```

The official marketplace pins each plugin to a specific commit. Changes in this
repository become available through `claude-plugins-official` after the Railway
entry in `anthropics/claude-plugins-official` is updated to a commit that
contains them.

To install the version published by this repository's Claude Code marketplace,
add the marketplace and install the `railway` plugin from it:

```text
/plugin marketplace add railwayapp/railway-skills
/plugin install railway@railway-skills
/reload-plugins
```

### Cursor

Install from the official [Cursor Marketplace](https://cursor.com/marketplace/railway):

```text
/add-plugin railway
```

To install the version published by this repository directly instead, add it
as a plugin source from Cursor settings:

1. Open **Settings**.
2. Select **Plugins**.
3. Paste `https://github.com/railwayapp/railway-skills` in the **Search or Paste Link** input.
4. Click the Railway plugin.
5. Click **Add to Cursor**.

- Plugin manifest: [`plugins/railway/.cursor-plugin/plugin.json`](plugins/railway/.cursor-plugin/plugin.json)
- Marketplace: [`.cursor-plugin/marketplace.json`](.cursor-plugin/marketplace.json)

### Grok Build

Railway is published in the [official xAI plugin
marketplace](https://github.com/xai-org/plugin-marketplace). Install it from
Grok's TUI:

1. Run `grok`.
2. Open the extensions modal with `/plugins`.
3. Go to the **Marketplace** tab.
4. Select `railway` from the marketplace.
5. Press `i` to install.

The official marketplace entry resolves the nested plugin at `plugins/railway`
from this repository and pins it to a specific commit.

## Skill surface

This repo ships one installable skill:

- [`use-railway`](plugins/railway/skills/use-railway/SKILL.md)

`use-railway` is route-first. Intent routing is defined in `SKILL.md`, and execution details are split into action-oriented references.

It includes database design references for Postgres, MySQL, Redis, and MongoDB covering schema and data types, indexing, query patterns, locking, safe migrations, and when to use high availability, connection pooling, and point-in-time recovery on Railway.

## License

MIT
