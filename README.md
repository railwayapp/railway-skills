# Railway Skills

Agent skills for [Railway](https://railway.com), following the [Agent Skills](https://agentskills.io) format. 

This repository also includes Railway plugin packaging for Claude Code, OpenAI Codex, Grok Build, and Cursor. The plugin includes Agent Skills and local MCP configuration.


## Railway agent setup (Installing Agent Skills and local MCP)

To configure Railway agent support through the Railway CLI, run:

```bash
curl -fsSL agents.railway.com | sh
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

## Installing the Railway Plugin

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

Codex support in this repository is packaged through the repo-local Codex marketplace manifest. The manifest makes the `railway` plugin available to
Codex environments that load this repository's plugin marketplace:

- Plugin manifest: [`plugins/railway/.codex-plugin/plugin.json`](plugins/railway/.codex-plugin/plugin.json)
- Marketplace: [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json)

Add this GitHub repository as a Codex marketplace:

1. Open Codex.
2. Select **Plugins** in the sidebar.
3. Open the **More** dropdown.
4. Click **Add more**.
5. Enter [`railwayapp/railway-skills`](https://github.com/railwayapp/railway-skills) as the marketplace source.

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

### Grok Build

Railway is packaged for Grok as the nested plugin at `plugins/railway`.
Marketplace entries should point at that subpath with a pinned commit:

```json
{
  "name": "railway",
  "source": {
    "source": "url",
    "url": "https://github.com/railwayapp/railway-skills.git",
    "sha": "<full commit sha>",
    "path": "plugins/railway"
  }
}
```

After the Railway entry is available in a Grok marketplace, install it from Grok's TUI:

1. Run `grok`.
2. Open the extensions modal with `/plugins`.
3. Go to the **Marketplace** tab.
4. Select `railway` from the marketplace.
5. Press `i` to install.

## Skill surface

This repo ships one installable skill:

- [`use-railway`](plugins/railway/skills/use-railway/SKILL.md)

`use-railway` is route-first. Intent routing is defined in `SKILL.md`, and execution details are split into action-oriented references.

## License

MIT
