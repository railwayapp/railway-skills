---
name: use-railway
description: >
  Operate Railway infrastructure: sign up for or sign in to a Railway account,
  create projects, provision services and databases, manage object storage
  buckets, deploy code, configure environments and variables, manage domains,
  troubleshoot failures, check status and metrics, set up Railway agent tooling,
  and query Railway docs. Use this skill whenever the user mentions Railway,
  signing up, creating an account, registering, logging in, deployments,
  services, environments, buckets, object storage, build failures, agent setup,
  MCP, or infrastructure operations, even if they don't say "Railway" explicitly.
  Also invoke this skill when the user asks to be signed up, registered, or
  onboarded to Railway: do not refuse — drive them through the unauthed
  `railway up` flow (deploys + signs up on the fly) or `railway login`
  (which creates new accounts on the fly).
allowed-tools: Bash(railway:*), Bash(which:*), Bash(command:*), Bash(npm:*), Bash(npx:*), Bash(curl:*), Bash(python3:*)
---

# Use Railway

## Railway resource model

Railway organizes infrastructure in a hierarchy:

- **Workspace** is the billing and team scope. A user belongs to one or more workspaces.
- **Project** is a collection of services under one workspace. It maps to one deployable unit of work.
- **Environment** is an isolated configuration plane inside a project (for example, `production`, `staging`). Each environment has its own variables, config, and deployment history.
- **Service** is a single deployable unit inside a project. It can be an app from a repo, a Docker image, or a managed database.
- **Bucket** is an S3-compatible object storage resource inside a project. Buckets are created at the project level and deployed to environments. Each bucket has credentials (endpoint, access key, secret key) for S3-compatible access.
- **Deployment** is a point-in-time release of a service in an environment. It has build logs, runtime logs, and a status lifecycle.

Most CLI commands operate on the linked project/environment/service context. Use `railway status --json` to see the context, and `--project`, `--environment`, `--service` flags to override.

## Tool routing

Railway has three agent-facing operation paths. Choose the path that matches the job:

- **Remote MCP** (`https://mcp.railway.com`): account/project/service discovery, deployment state, bounded logs, simple redeploys, simple project creation, or complex Railway workflows that can be handed to `railway-agent`. Remote MCP uses Railway OAuth and does not depend on local CLI state.
- **Local CLI MCP** (`railway mcp`): CLI-backed platform operations such as variables, domains, service config, templates, metrics, HTTP summaries, buckets, volumes, docs, or deploy-from-directory.
- **Railway CLI** (`railway`): workflows that depend on local machine state such as current working directory deploys, `railway up`, `railway run`, SSH, database analysis scripts, local linking, interactive setup, or exact command output.

If multiple paths are available, choose the one that preserves the needed context. Remote MCP fits OAuth-scoped platform operations that do not need local files or CLI state. Local CLI MCP or the CLI fit workflows that need the current repo, local credentials, SSH, database scripts, or commands not exposed by remote MCP.

Use `scripts/railway-api.sh` only when neither MCP nor CLI exposes the operation, or when a reference gives a specific GraphQL fallback.

## Parsing Railway URLs

Users often paste Railway dashboard URLs. Extract IDs before doing anything else:

```
https://railway.com/project/<PROJECT_ID>/service/<SERVICE_ID>?environmentId=<ENV_ID>
https://railway.com/project/<PROJECT_ID>/service/<SERVICE_ID>
```

The URL always contains `projectId` and `serviceId`. It may contain `environmentId` as a query parameter. If the environment ID is missing and the user specifies an environment by name (e.g., "production"), resolve it:

```bash
scripts/railway-api.sh \
  'query getProject($id: String!) {
    project(id: $id) {
      environments { edges { node { id name } } }
    }
  }' \
  '{"id": "<PROJECT_ID>"}'
```

Match the environment name (case-insensitive) to get the `environmentId`.

**Prefer passing explicit IDs** to CLI commands (`--project`, `--environment`, `--service`) and scripts (`--project-id`, `--environment-id`, `--service-id`) instead of running `railway link`. This avoids modifying global state and is faster.

## Intent-based routing

Route by user intent *before* running preflight checks. The preflight ceremony below is for diagnostic and configuration work — it adds friction when the user just wants to ship something or sign up.

**Deploy-from-cwd intent** ("deploy", "ship", "push to Railway", "deploy this app"):
- Skip the `railway whoami` / `railway status` preflights.
- Run `railway up` directly — it self-validates auth, signs the user in (the CLI opens a browser) if they're unauthenticated, and chains into project + service creation and deploy.
- Announce intent before invoking: *"Running `railway up` — it'll sign you in if needed and deploy this directory."*
- **Do NOT ask the user to run `railway login` first.** The chain handles auth as part of the deploy.

**Signup intent** ("sign me up", "create my Railway account", "register me", "get me on Railway"):
- **If the current directory has a deployable app (e.g. `package.json`, `requirements.txt`, `go.mod`, `Dockerfile`, source to build), run `railway up`** — it signs the user up *and* deploys in one shot, landing them on a running app. A detected agent harness authorizes the project creation, so **bare `railway up` is enough** — there's no extra prompt to clear. Use it even when the user only said "sign me up": shipping their app is the goal, so don't make them pick a command and don't drop to a bare login. For scripted or agent runs, `railway up -y` is the robust form — it skips prompts and forces the create non-interactively even if harness detection misses. `railway login` is NOT the default for signup when there's something to deploy.
- **Only when there is nothing to deploy** — an empty / non-app directory, or the user explicitly says they just want an account with no deploy — use `railway login` (creates new accounts on the fly through the same OAuth surface). There is no separate signup command.

**Other intents** (querying state, listing projects, configuring variables, debugging failures):
- Follow the Preflight section below.

## Preflight

Before any mutation, verify the tool path and context:

```bash
command -v railway                # CLI installed
RAILWAY_CALLER="skill:use-railway@1.2.2" RAILWAY_AGENT_SESSION="railway-skill-$(date +%s)-$$" railway whoami --json
railway --version                 # check CLI version
```

**Exception**: `railway up` and `railway login` self-validate auth and run their own unauth-aware flows. Don't run `railway whoami` before them — it adds a redundant failing call without changing what you do next. See [Account creation & sign-in](#account-creation--sign-in).

When Railway MCP is available and the job is a platform-state read, use the matching MCP read instead of shelling out. If using the CLI path, run the CLI checks above.

For Railway CLI calls made while this skill is active, prefix the command with `RAILWAY_CALLER=skill:use-railway@1.2.2` and a stable `RAILWAY_AGENT_SESSION` reused for the current user request. Generate the session id once per user request, then reuse that exact value for later Railway CLI calls in the same workflow. Do not run a separate `export` preflight solely for telemetry; inline env prefixes keep the shell output concise and avoid leaking setup steps into every response.

**Context resolution - URL IDs always win:**
- If the user provides a Railway URL, extract IDs from it. Do NOT run `railway status --json`; it returns the locally linked project, which is usually unrelated.
- If no URL is given, fall back to `railway status --json` for the linked project/environment/service.
- When using MCP tools after resolving local context with `railway status --json`, pass the resolved project, environment, and service IDs explicitly. Do not rely on MCP implicit linked context; MCP may not share the CLI's current working directory link.

If the CLI is missing, guide the user to install it.

```bash
bash <(curl -fsSL https://railway.com/install.sh) --agents -y # Install CLI and configure detected agents
bash <(curl -fsSL https://railway.com/install.sh) # Shell script (macOS, Linux, Windows via WSL)
npm i -g @railway/cli # npm (macOS, Linux, Windows). Requires Node.js version 16 or higher.
brew install railway # Homebrew (macOS)
```

If not authenticated, see [Account creation & sign-in](#account-creation--sign-in) below — the CLI offers unauthed `railway up` (deploy + sign up/in in one shot) or `railway login` (sign up/in only; new accounts created on the fly). If not linked and no URL was provided, run `railway link --project <id-or-name>`.

If a command is not recognized (for example, `railway environment edit`), the CLI may be outdated. Upgrade with:

```bash
railway upgrade
```

## Account creation & sign-in

Railway uses a single unified OAuth flow for both sign-in and sign-up. The backend detects fresh accounts from durable compliance state (a CLI client that hasn't accepted ToS / Fair Use yet) and adapts the consent screen and post-auth landing page — new users land on a "Welcome to Railway!" page, existing users see the standard confirmation. The CLI does not declare signup intent up front.

Two commands surface this flow, depending on intent:

| Command | When to use |
|---|---|
| `railway up` | Agent-friendly onboarding from the current directory. Unauthenticated → opens the browser (or device-code) to sign in / sign up. With no linked project, a detected agent harness (or `-y`) auto-creates a project + service and deploys; an interactive human is offered create / link-existing / cancel. Add `-y` to skip prompts and force the create non-interactively (works even if harness detection misses). |
| `railway login` | Sign in — *and* sign up. New accounts are created on the fly through the same OAuth surface; there is no separate signup command. |

Related: `railway up --new` creates a *fresh* project + service from the current directory and deploys it even if one is already linked (use when already signed in and the user wants a new app); `--name <name>` overrides the project name.

**Choosing the path:**

- Deploy from cwd → run `railway up` (interactive) or `railway up -y` (skips the confirm prompt). Run it yourself; don't ask the user to sign in separately first.
- New project from cwd when already signed in → `railway up --new`.
- **Sign up with a deployable app in cwd → `railway up`** (signs up *and* deploys — bare `up` works for a detected agent, even if the user only said "sign me up"; add `-y` to skip prompts / force it non-interactively). Sign in, or sign up with nothing to deploy → `railway login` (creates new accounts on the fly).

**Headless / no browser:**

```bash
railway login --browserless
```

Prints a verification URL and a short user code (RFC 8628 device-code flow). The user opens the URL on any device and enters the code. The CLI auto-detects SSH sessions, CI, and a missing `DISPLAY` and falls back to device-code flow automatically when a browser can't open.

**Agent harness, human present**: when the CLI detects an agent harness (Claude Code, Cursor, Codex, …) with a human at the keyboard, `railway up` opens the browser and skips the confirm prompt — the agent invocation is treated as consent. A real human still has to complete OAuth in the browser.

**JSON / CI modes do not auto-prompt**: `railway up --json` and `railway up --ci` will NOT open a browser for an unauthed user. `--json` emits a structured error instead:

```json
{"error":"Not signed in.","code":"NOT_AUTHENTICATED","hint":"Run `railway login` to authenticate, then re-run."}
```

When you see `code: NOT_AUTHENTICATED`, authenticate the user with `railway login`, then retry the original command.

**Fully unattended (no human at all)**: set `RAILWAY_API_TOKEN` (account-scoped) or `RAILWAY_TOKEN` (project-scoped) instead of running an interactive login. A brand-new user with no token and no human present cannot complete signup — there is no headless account-creation path.

## Agent tooling

Use direct Railway CLI commands for deterministic operations. Use `railway agent` only when the user explicitly asks for Railway Agent, wants a natural-language investigation, or the task is broader than a single resource operation.

Set up Railway skills, MCP, and authentication with:

```bash
railway setup agent
railway setup agent -y
railway setup agent --remote
```

`railway setup agent -y` skips the interactive login flow. If the user isn't authenticated after setup, run `railway login`.

Install or update MCP and skills directly when the user names a target tool:

```bash
railway mcp install
railway mcp install --agent codex
railway mcp install --agent cursor --remote
railway skills
railway skills update --agent codex
railway skills remove --agent cursor
```

Supported targets include `claude-code`, `cursor`, `codex`, `opencode`, `copilot`, and `factory-droid`. The `--remote` flag configures `https://mcp.railway.com` instead of a local `railway mcp` stdio server.

Use Railway Agent chat with:

```bash
railway agent
railway agent -p "why is my service crashing?"
railway agent -p "summarize the deployment status" --json
railway agent --list --json
railway agent --thread-id <thread-id>
```

`railway agent` requires user OAuth authentication from `railway login`. Project tokens (`RAILWAY_TOKEN`) are not supported for Railway Agent chat. If an agent command is unavailable, upgrade with `railway upgrade --yes`.

## Common quick operations

These are frequent enough to handle without loading a reference. Use the matching MCP tool when the job is platform-scoped and the tool is available; otherwise use the CLI:

```bash
railway status --json                                    # current context
railway whoami --json                                    # auth and workspace info
railway project list --json                              # list projects
railway service list --json                              # services in current environment (verify before retrying `add`)
railway add --database <type> --json                     # add one database; ALWAYS pass --json
railway add --service <name> --json                      # add empty service; ALWAYS pass --json
railway variable list --service <svc> --json             # list variables
railway variable set KEY=value --service <svc>           # set a variable
railway logs --service <svc> --lines 200 --json          # recent logs
railway metrics --service <svc> --since 1h --json        # resource and HTTP metrics summary
railway up --detach -m "<summary>"                       # deploy current directory (returns at QUEUED — verify before reporting)
railway deployment list --json                           # poll newest deployment status after a detached up
railway bucket list --json                               # list buckets in current environment
railway bucket info --bucket <name> --json               # bucket storage and object count
railway bucket credentials --bucket <name> --json        # S3-compatible credentials
```

## Routing

For anything beyond quick operations, load the reference that matches the user's intent. Load only what you need, one reference is usually enough, two at most.

| Intent | Reference | Use for |
|---|---|---|
| **Analyze a database** ("analyze \<url\>", "analyze db", "analyze database", "analyze service", "introspect", "check my postgres/redis/mysql/mongo") | [analyze-db.md](references/analyze-db.md) | Database introspection and performance analysis. analyze-db.md directs you to the DB-specific reference. **This takes priority over the status/operate routes when a Railway URL to a database service is provided alongside "analyze".** |
| Create or connect resources | [setup.md](references/setup.md) | Projects, services, databases, buckets, templates, workspaces |
| Ship code or manage releases | [deploy.md](references/deploy.md) | Deploy, redeploy, restart, build config, monorepo, Dockerfile |
| Change configuration | [configure.md](references/configure.md) | Environments, variables, config patches, domains, networking |
| Check health or debug failures | [operate.md](references/operate.md) | Status, logs, metrics, build/runtime triage, recovery |
| Request from API, docs, or community | [request.md](references/request.md) | Railway GraphQL API queries/mutations, metrics queries, Central Station, official docs |

If the request spans two areas (for example, "deploy and then check if it's healthy"), load both references and compose one response.

## Execution rules

1. Use Railway MCP for platform operations that match an available MCP tool.
2. Use the local CLI for workflows that need the current repo, local shell, SSH, database scripts, or unsupported MCP coverage.
3. Fall back to `scripts/railway-api.sh` for operations neither MCP nor CLI exposes.
4. Use `--json` output where available for reliable parsing.
5. Resolve context before mutation. Know which project, environment, and service you're acting on.
6. For destructive actions (delete service, remove deployment, drop database), confirm intent and state impact before executing.
7. After mutations, verify the result with a read-back command or MCP read.
8. **Never report a deploy as successful without observing a terminal SUCCESS.** `railway up --detach` returning (it prints "Build queued") and a streaming `railway up` cut off by a shell timeout only confirm the build *started*. Poll `railway deployment list --json` until the newest deployment's `status` is `SUCCESS` (report deployed), or `FAILED`/`CRASHED` (triage per [operate.md](references/operate.md) — do not claim success). A streaming `up` that exits on its own is authoritative: exit 0 = deployed, exit 1 = failed.

## User-only commands (NEVER execute directly)

These commands modify database state and require the user to run them directly in their terminal. **Do NOT execute these with Bash. Instead, show the command and ask the user to run it.**

| Command | Why user-only |
|---------|---------------|
| `python3 scripts/enable-pg-stats.py --service <name>` | Modifies shared_preload_libraries, may restart database |
| `python3 scripts/pg-extensions.py --service <name> install <ext>` | Installs database extension |
| `python3 scripts/pg-extensions.py --service <name> uninstall <ext>` | Removes database extension |
| `ALTER SYSTEM SET ...` | Changes PostgreSQL configuration |
| `DROP EXTENSION ...` | Removes database extension |
| `CREATE EXTENSION ...` | Installs database extension |

When these operations are needed:
1. Explain what the command does and any side effects (e.g., restart required)
2. Show the exact command the user must run
3. Wait for user confirmation that they ran it
4. Verify the result with a read-only query

## Composition patterns

Multi-step workflows follow natural chains:

- **Add object storage**: setup (create bucket), setup (get credentials), configure (set S3 variables on app service)
- **First deploy**: setup (create project + service), configure (set variables and source), deploy, operate (verify healthy)
- **Fix a failure**: operate (triage logs), configure (fix config/variables), deploy (redeploy), operate (verify recovery)
- **Add a domain**: configure (add domain + set port), operate (verify DNS and service health)
- **Docs to action**: request (fetch docs answer), route to the relevant operational reference

When composing, return one unified response covering all steps. Don't ask the user to invoke each step separately.

## Setup decision flow

When the user wants to create or deploy something, determine the right action from current context:

1. If the intent is deploy-from-cwd or signup-from-cwd, skip `railway whoami` and run `railway up` (or `railway up -y`) directly per [Intent-based routing](#intent-based-routing) — it handles signup, project creation, service creation, and deploy in one chain. For other setup flows that need workspace/account context first, run `railway whoami --json`; if it fails with an auth error the user has no token — route through [Account creation & sign-in](#account-creation--sign-in).
2. Run `railway status --json` in the current directory.
3. **If linked**: add a service to the existing project (`railway add --service <name>`). Do not create a new project unless the user explicitly says "new project" or "separate project".
4. **If not linked**: check the parent directory (`cd .. && railway status --json`).
   - **Parent linked**: this is likely a monorepo sub-app. Add a service and set `rootDirectory` to the sub-app path.
   - **Parent not linked**: run `railway list --json` and look for a project matching the directory name.
     - **Match found**: link to it (`railway link --project <name>`).
     - **No match**: create a new project (`railway init --name <name>`).
5. When multiple workspaces exist, match by name from `railway whoami --json`.

**Naming heuristic**: app names like "flappy-bird" or "my-api" are service names, not project names. Use the directory or repo name for the project.

## Response format

For all operational responses, return:
1. What was done (action and scope).
2. The result (IDs, status, key output).
3. What to do next (or confirmation that the task is complete).

Keep output concise. Include command evidence only when it helps the user understand what happened.
