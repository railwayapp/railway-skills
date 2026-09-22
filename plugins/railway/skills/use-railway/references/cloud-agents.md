# Cloud agents

Use `railway ca` / `railway code` to run coding harnesses on persistent Railway cloud agent VMs. Use `railway agent` for Railway Agent chat/investigations, and [sandbox.md](sandbox.md) for sandbox execution, builds, and checkpoints.

## Availability and target

Cloud agents arrived in CLI 5.32; flat lifecycle commands in 5.35 and desktop setup in 5.38. They are experimental and require **Cloud Agents** enabled in [Priority Boarding](https://railway.com/account/feature-flags). A feature-availability error calls for enabling that feature, not repeatedly provisioning VMs or changing project feature flags.

Use explicit project and environment for creation. A directory's `railway link` context takes precedence over the saved default project; a stale link can fall back to the saved default. Verify the target rather than assuming the saved preference wins. Interactive `ca` can run login and continue; noninteractive unauthenticated calls fail instead of waiting on an unattended device code.

```bash
railway ca setup --show
railway ca list --json
railway ca list --project <project-id> --environment <env> --json
```

Bare `list` finds the user's agents across projects. `--all` includes other members' agents and requires an explicit environment. Address an existing agent by name or ID; an omitted identifier uses the directory's agent or the sole candidate, otherwise the CLI reports candidates.

## Create, launch, and connect

```bash
railway ca create my-agent --project <project-id> --environment <env> --json
railway ca create my-agent --project <project-id> --environment <env> --env-file .env.agent --json
railway ca ssh my-agent
railway ca ssh my-agent -- bash
railway ca start --codex --project <project-id> --environment <env>
railway ca start --railway --project <project-id> --environment <env>
```

Choose one creation command with the needed options. `create` provisions a VM without attaching; `ssh` connects to an existing VM and does not create one for a mistyped name. `start` can create and launch a harness, skipping the TUI. Harness flags are `--codex`, `--claude`, `--grok`, and `--railway`; the first three carry or mint a local sign-in, while `--railway` launches Railway's own agent with credentials already on the VM and needs no local sign-in, which suits unattended workflows. `--no-wait` on create/wake means requested, not ready: reread `ca list --json` before reporting readiness. Environment files and `--variable` inputs configure the agent VM; pass only values needed for the remote task.

For a human terminal, bare `railway ca` opens the management TUI and `railway code` opens a session-focused view. Automated workflows should use explicit lifecycle commands rather than attempting to control that TUI. `ca setup` configures the default harness and skills; `ca setup --show` inspects preferences and `ca setup --reset` removes them when requested. Launching can carry harness authentication and skills from the local machine, so choose the harness and remote target deliberately.

## Credentials inside the VM

The VM ships the `railway` CLI, the `gh` CLI and the `railway` MCP server. The MCP server is authenticated in every session. The `railway` CLI is authenticated only inside an SSH terminal session (`railway ca ssh`, `railway code`, desktop SSH), which injects the user's token; a chat session started from the Railway dashboard or mobile app carries no CLI credential, by design. An agent working in such a session must not run `railway` commands, `railway api` included, and should use the MCP tools instead. `railway login` and `railway link` never help on the VM and fail in its non-interactive shell.

## Sleep, wake, and delete

```bash
railway ca wake my-agent
railway ca sleep my-agent
railway ca delete my-agent
```

Sleep stops compute while retaining the disk; deletion removes the agent and its disk. Use sleep when the user wants to pause work and keep files. `sleep --all` acts across the user's running agents unless narrowed by environment; use it only when that broader scope was requested. Check `list --json` after lifecycle mutations. Do not mistake a disconnected harness session for a deleted VM.

## Desktop SSH setup

```bash
railway ca desktop --codex --agent my-agent --dry-run
railway ca desktop --codex --agent my-agent
railway ca desktop --claude --agent my-agent
```

Choose the requested app; both flags can configure both on the same VM. The dry-run previews configuration. Actual setup prepares the remote harness and writes an OpenSSH entry; Claude setup also writes its desktop settings. Omitting `--agent` can create an agent when none exists. `--dir /app/api` selects the remote working directory. Restart the desktop app after setup.

A desktop app cannot wake a sleeping agent through the relay: run `railway ca wake <name>` before connecting. To undo the local integration, use `railway ca desktop --codex --agent my-agent --remove` (or `--claude`); removing desktop configuration is distinct from deleting the VM.

## Troubleshoot

- **Wrong project**: inspect the directory link and `ca setup --show`, then use explicit scope.
- **Access blocked**: check Cloud Agents in Priority Boarding; project feature flags do not enable it.
- **Desktop cannot connect**: confirm the agent is awake, inspect the generated SSH host, and check CLI SSH access before rerunning setup.
- **Session ended unexpectedly**: inspect `ca list` and reconnect to the existing agent before creating another VM.

## Validated against

- Docs: [Cloud agent CLI](https://docs.railway.com/cli/ca), [Code CLI](https://docs.railway.com/cli/code)
- CLI source (v5.49.1): [cloud_agent/mod.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/cloud_agent/mod.rs), [lifecycle.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/cloud_agent/lifecycle.rs), [desktop.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/cloud_agent/desktop.rs), [setup.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/cloud_agent/setup.rs), [access.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/cloud_agent/access.rs)
