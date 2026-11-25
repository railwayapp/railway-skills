# Setup

Create, link, and organize Railway projects, services, databases, and workspaces.

## Account creation & first-time onboarding

A brand-new user with no Railway account is onboarded through the same unified OAuth flow as sign-in — the backend detects fresh accounts and adapts the consent + landing pages. Pick the command by intent:

- **Deploy from the current directory** → `railway up` (interactive) or `railway up -y` (skips the confirm prompt). When unauthenticated it opens a browser to sign in / sign up, then creates a project + service and deploys. Run it yourself; do not ask the user to `railway login` first.
- **New project from cwd when already signed in** → `railway up --new` (`--name <name>` to override the project name).
- **Sign up with a deployable app in cwd → `railway up`** (signs up *and* deploys — bare `up` works for a detected agent, even if the user only said "sign me up"; add `-y` to skip prompts / force it non-interactively). Sign in, or sign up with nothing to deploy → `railway login` (creates new accounts on the fly).

`railway up` and `railway login` self-validate auth — don't run `railway whoami` before them.

**Headless / SSH / CI**: the CLI auto-detects these and switches to the device-code flow (RFC 8628: sign-in link + short code) on its own. Do NOT pass `--browserless` just because you are an agent — if the human is at this machine, bare `railway login` opens their browser and completes far more reliably. Reserve the flag for machines with genuinely no browser that the auto-detection missed.

**`railway up --json` / `--ci` do NOT auto-prompt** an unauthed user. `--json` emits a structured `{"error":"Not signed in.","code":"NOT_AUTHENTICATED", ...}` on stdout and exits non-zero — detect `NOT_AUTHENTICATED`, run `railway login`, then retry.

**Fully unattended (no human)**: set `RAILWAY_API_TOKEN` (account-scoped) or `RAILWAY_TOKEN` (project-scoped) instead of logging in. There is no headless account-creation path — a brand-new user needs a human at the browser once.

## Projects

### List and discover

```bash
railway project list --json        # projects in current workspace
railway list --json                # all projects across workspaces with service metadata
railway whoami --json              # current user, workspace memberships
```

### Link to an existing project

Linking sets the working context for all subsequent CLI commands in this directory.

```bash
railway link --project <project-id-or-name>
railway status --json              # confirm linked context
```

Without `--project`, `railway link` runs interactively. For scripted or CI use, always pass explicit flags.

### Link to a specific service

Switch the linked service within an already-linked project:

```bash
railway service link              # interactive service picker
railway service link <name>       # link directly by name
```

### Create a new project

```bash
railway init --name <project-name>
railway init --name <project-name> --workspace <workspace-id-or-name>
```

`railway init` both creates and links in one step. In CI or multi-workspace setups, pass `--workspace` explicitly to avoid ambiguity.

### Update project settings

Settings like project name, PR deploys, and visibility have no dedicated CLI command. Use `railway api` (see [request.md](request.md)):

```bash
railway api \
  'mutation updateProject($id: String!, $input: ProjectUpdateInput!) {
    projectUpdate(id: $id, input: $input) { id name isPublic prDeploys }
  }' \
  --variables '{"id":"<project-id>","input":{"name":"new-name","prDeploys":true}}'
```

## Services

### List services

Use `railway service list` for service discovery. It returns services in the current environment by default.

```bash
railway service list --json
railway service list --project <project-id> --environment production --json
```

Prefer service IDs from JSON output when names may collide.

### Create a service

```bash
railway add --service <name> --json           # empty service
railway add --database postgres --json        # standalone managed database (postgres, redis, mysql, mongo); for HA see databases.md
railway add                                   # interactive only — do not use non-interactively
```

**Always pass `--json` to `railway add`.** Without it, a successful database create writes nothing to stdout — only a `> What do you need? Database` echo on stderr that looks identical to a stalled interactive prompt. Retrying based on "no stdout came back" silently provisions a second database. With `--json`, success prints `{"serviceId":"…","serviceName":"…"}` and failure exits non-zero.

**`--database` is cumulative, not last-wins.** `railway add --database postgres --database redis` creates *both* in a single call. Don't repeat the flag — issue one `railway add` per database.

**If `railway add` output looks ambiguous, never retry blind.** Run `railway service list --json` (or query `project.services` via [request.md](request.md)) first and compare against what you expected to exist. Treat the service list as the source of truth, not the CLI's stdout shape.

Before adding a database — and before retrying any `railway add` whose output you can't interpret — list existing services to avoid duplicates. Run `railway service list --json` for a fast count, or `railway environment config --json` and inspect `source.image` per service when you need to identify the engine:

| Image pattern | Database |
|---|---|
| `ghcr.io/railway/postgres*` or `postgres:*` | Postgres |
| `ghcr.io/railway/redis*` or `redis:*` | Redis |
| `ghcr.io/railway/mysql*` or `mysql:*` | MySQL |
| `ghcr.io/railway/mongo*` or `mongo:*` | MongoDB |

If a matching database already exists, skip creation and wire the existing service's variables to the app.

Empty services have no source until you configure one. This is the right pattern when you need to set source repo, branch, or build config before the first deploy.

### Connect a database to a service

After `railway add --database <type>`, the database creates connection variables automatically. Wire them to your app service using variable references:

| Database | Connection variable |
|---|---|
| Postgres | `${{Postgres.DATABASE_URL}}` |
| Redis | `${{Redis.REDIS_URL}}` |
| MySQL | `${{MySQL.MYSQL_URL}}` |
| MongoDB | `${{MongoDB.MONGO_URL}}` |

```bash
railway variable set DATABASE_URL='${{Postgres.DATABASE_URL}}' --service <app-service>
```

Service names in variable references are case-sensitive and must match exactly. For full wiring details including public/private networking decisions, see [configure.md](configure.md).

When creating new service instances via JSON config patches, include `isCreated: true` in the service block to mark it as a new service.

### Connect to a database shell

Use `railway connect` when the user wants an interactive database shell (`psql`, `redis-cli`, `mysql`, or `mongosh`):

```bash
railway connect <database-service>
railway connect <database-service> --environment production
railway connect <database-service> --project <project-id> --environment production
railway connect <database-service> --ssh
railway connect <database-service> --no-ssh
```

The local database client must be installed for a shell. By default, `connect` uses a public TCP proxy when one exists and falls back to an SSH tunnel when no public proxy URL is available. Use `--ssh` to force the tunnel path, or `--no-ssh` to require a public TCP proxy.

For TablePlus, DBeaver, pgAdmin, or another GUI, CLI 5.27+ can hold a private tunnel open without starting or requiring a local database CLI:

```bash
railway connect <database-service> --tunnel-only --port 15432 --project <project-id> --environment production
```

`--tunnel-only` implies SSH and conflicts with `--no-ssh`. Omit `--port` to choose an available ephemeral port. Use the printed local connection details in the GUI; they include credentials, so do not echo them into a report. Keep the process running while the GUI is connected and stop it when finished. With `--project`, always supply `--environment`.

For backups, PITR, HA conversion/scaling, or connection pooling, load [databases.md](databases.md). A new database with high availability is not created here: deploy the engine's HA template directly, as [A new database](databases.md#a-new-database) describes.

### Delete a service

Deleting a service removes it from the target environment. Confirm with the user before running it.

```bash
railway service delete --service <service> --environment <env> --yes --json
railway service delete --service <service-id> --project <project-id> --environment <env> --yes --json
```

If 2FA is enabled and the command runs non-interactively, pass `--2fa-code <code>`.

### Deploy from a template

Templates provision pre-configured services with sensible defaults, faster than creating an empty service and configuring it manually. Use `templates search` for marketplace discovery and `deploy --template` for deployment:

```bash
railway templates search postgres --verified true --json
railway templates search --category Storage --limit 10 --json
railway templates search postgres --limit 50 --after <cursor> --json
railway deploy --template <template-code>
```

The template search command doesn't require authentication. Use the `code` from the JSON results with `railway deploy --template <template-code>`.

Template deployments typically create:

- A service with pre-configured image or source
- Environment variables (connection strings, secrets)
- A volume for persistent data (databases)
- A TCP proxy for external access (where applicable)

Manage owned templates with:

```bash
railway templates list --json
railway templates list --workspace <workspace> --json
railway templates create --project <project> --environment production --json
railway templates publish <template-id> --category Other --description "Deploy and Host My App with Railway" --readme-file README.md --json
railway templates update <template-id> --category Other --description "Updated description" --readme-file README.md --json
railway templates unpublish <template-id-or-code> --yes --json
railway templates delete <template-id-or-code> --yes --json
```

Non-interactive `unpublish` and `delete` require `--yes`; pass `--2fa-code` when required by the current auth session.

### Bootstrap source for an empty service

After creating an empty service, wire it to a repo:

```bash
railway environment edit --service-config <service> source.repo <repo-url>
railway environment edit --service-config <service> source.branch <branch>
```

### Deploy a Docker image

When you have a built image (for example, from a private registry or Docker Hub), skip source builds entirely:

```bash
railway environment edit --service-config <service> source.image <image:tag>
```

This sets the service to pull from a container registry instead of building from source.

## Buckets

Buckets are S3-compatible object storage. They are created at the project level and deployed to environments via config patches.

### List buckets

```bash
railway bucket list --json                                # buckets in current environment
railway bucket list --environment production --json       # buckets in a specific environment
```

### Create a bucket

```bash
railway bucket create my-bucket --region sjc              # create with name and region
railway bucket create --region iad --json                 # auto-named, JSON output
```

Available regions:

| Code | Location |
|---|---|
| `sjc` | US West (California) |
| `iad` | US East (Virginia) |
| `ams` | EU West (Amsterdam) |
| `sin` | Asia Pacific (Singapore) |

Without `--region`, the CLI prompts interactively. For scripted use, always pass `--region`.

### Delete a bucket

Deletion is permanent and destroys all objects in the bucket.

```bash
railway bucket delete --bucket my-bucket --yes            # non-interactive
railway bucket delete --bucket my-bucket --yes --2fa-code 123456   # with 2FA
```

### Rename a bucket

```bash
railway bucket rename --bucket my-bucket --name new-name --json
```

### Bucket info

Check storage usage and object count:

```bash
railway bucket info --bucket my-bucket --json
```

Returns storage size (bytes), object count, region, and environment.

### Bucket credentials

Get S3-compatible credentials for connecting your app to a bucket:

```bash
railway bucket credentials --bucket my-bucket --json
```

Returns: `endpoint`, `accessKeyId`, `secretAccessKey`, `bucketName`, `region`, `urlStyle`.

Without `--json`, output uses `AWS_*=value` lines suitable for `eval $(railway bucket credentials)` or piping into `.env` files.

To reset credentials (invalidates existing ones):

```bash
railway bucket credentials --bucket my-bucket --reset --yes
railway bucket credentials --bucket my-bucket --reset --yes --2fa-code 123456  # with 2FA
```

### Connect a bucket to a service

After creating a bucket, wire the S3 credentials to your app service as environment variables:

```bash
# Get credentials
railway bucket credentials --bucket my-bucket --json

# Set them on your app service
railway variable set \
  AWS_ENDPOINT_URL=<endpoint> \
  AWS_ACCESS_KEY_ID=<access-key> \
  AWS_SECRET_ACCESS_KEY=<secret-key> \
  AWS_S3_BUCKET_NAME=<bucket-name> \
  AWS_DEFAULT_REGION=<region> \
  --service <app-service>
```

All subcommands support `--bucket (-b)` and `--environment (-e)` as global flags to skip interactive prompts.

## Analyze codebase before setup

When setting up a new service from source, detect the project type from marker files:

| Marker file | Type |
|---|---|
| `package.json` | Node.js |
| `requirements.txt` or `pyproject.toml` | Python |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `index.html` (no package.json) | Static site |

### Monorepo detection

| Marker | Monorepo type |
|---|---|
| `pnpm-workspace.yaml` | pnpm workspace (shared) |
| `package.json` with `workspaces` field | npm/yarn workspace (shared) |
| `turbo.json` | Turborepo (shared) |
| Multiple subdirectories with separate `package.json`, no workspace config | Isolated monorepo |

**Isolated monorepo** (apps don't share code): set `rootDirectory` to the app's subdirectory (for example, `/apps/api`).

**Shared monorepo** (TypeScript workspaces, shared packages): do not set `rootDirectory`. Set custom build and start commands instead:

- pnpm: `pnpm --filter <package> build`
- npm: `npm run build --workspace=packages/<package>`
- yarn: `yarn workspace <package> build`
- Turborepo: `turbo run build --filter=<package>`

### Scaffolding hints

When no code exists, minimal starting points for common types:

- **Static site**: create `index.html` in the root directory.
- **Vite React**: `npm create vite@latest . -- --template react`
- **Python FastAPI**: create `main.py` with a FastAPI app and `requirements.txt` with `fastapi` and `uvicorn`.
- **Go**: create `main.go` with an HTTP server that reads `PORT` from the environment.

## Workspaces

Workspaces scope billing and team access. Most users have one personal workspace and possibly team workspaces.

```bash
railway whoami --json              # lists workspace memberships
```

When creating projects, Railway uses the default workspace unless `--workspace` is specified.

## Troubleshoot setup issues

- **CLI missing**: install via `brew install railway` or `bash <(curl -fsSL https://railway.com/install.sh)`
- **Not authenticated**: `railway login`
- **Project not found**: verify with `railway project list --json`, check workspace context
- **Service not found**: `railway service list --json` to list services in the current environment
- **Database shell cannot connect**: install the local database client, use `railway connect <service> --ssh`, or create/check a TCP proxy
- **Wrong workspace**: inspect `railway whoami --json`, re-run with explicit `--workspace`
- **Permission denied**: check workspace role, mutations require member or admin access

## Validated against

- Docs: [cli.md](https://docs.railway.com/cli), [init.md](https://docs.railway.com/cli/init), [add.md](https://docs.railway.com/cli/add), [link.md](https://docs.railway.com/cli/link), [project.md](https://docs.railway.com/cli/project), [service.md](https://docs.railway.com/cli/service), [connect.md](https://docs.railway.com/cli/connect), [templates.md](https://docs.railway.com/cli/templates), [list.md](https://docs.railway.com/cli/list), [whoami.md](https://docs.railway.com/cli/whoami)
- CLI source: [init.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/init.rs), [add.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/add.rs), [project.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/project.rs), [service.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/service.rs), [connect.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/connect.rs), [templates.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/templates.rs), [list.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/list.rs), [bucket.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/bucket.rs)
- API command: [api.rs (v5.49.1)](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/api.rs)
