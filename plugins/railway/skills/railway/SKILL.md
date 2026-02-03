---
name: railway
description: Deploy and manage applications on Railway. Use when user mentions railway, deploy, environment config, variables, env vars, metrics, logs, build logs, service status, deployment status, replicas, domains, databases, postgres, redis, or wants to create/configure projects and services.
allowed-tools: Bash(railway:*), Bash(which:*), Bash(command:*), Bash(npm:*), Bash(npx:*)
---

# Railway

Deploy and manage applications on Railway.

## Prerequisites

Check CLI installed:
```bash
command -v railway
```

If not installed:
> Install Railway CLI:
> ```
> npm install -g @railway/cli
> ```
> or
> ```
> brew install railway
> ```

Check authenticated:
```bash
railway whoami --json
```

If not authenticated:
> Run `railway login` to authenticate.

Requires CLI **v4.27.3+** for `environment edit`. Check with:
```bash
railway --version
```

If below 4.27.3:
```bash
railway upgrade
```

---

## Project & Service Setup

### Decision Flow

```
railway status --json (in current dir)
     │
┌────┴────┐
Linked    Not Linked
  │            │
  │       Check parent: cd .. && railway status --json
  │            │
  │       ┌────┴────┐
  │    Parent      Not linked
  │    Linked      anywhere
  │       │            │
  │   Add service   railway list
  │   Set rootDir      │
  │   Deploy       ┌───┴───┐
  │       │      Match?  No match
  │       │        │        │
  │       │      Link    Init new
  └───────┴────────┴────────┘
           │
    User wants service?
           │
     ┌─────┴─────┐
    Yes         No
     │           │
Scaffold code   Done
     │
railway add --service
     │
Configure if needed
     │
Ready to deploy
```

### Check Current State

```bash
railway status --json
```

- **If linked**: Add a service to the existing project
- **If not linked**: Check if a PARENT directory is linked

#### When Already Linked

**Default behavior**: "deploy to railway" = add a service to the linked project.

Do NOT create a new project unless user EXPLICITLY says "new project", "create a project", "separate project".

App names like "flappy-bird" or "my-api" are SERVICE names, not project names.

#### Parent Directory Linking

Railway CLI walks up the directory tree. If in a subdirectory:
```bash
cd .. && railway status --json
```

**If parent is linked**: Don't init/link the subdirectory. Instead:
1. Create service: `railway add --service <name>`
2. Set `rootDirectory` to subdirectory path via `environment edit`
3. Deploy from root: `railway up`

### Init vs Link

**Skip if already linked** — just add a service instead.

#### Check User's Projects

```bash
railway list --json
```

#### Decision Logic

1. **User explicitly says "new project"** → `railway init`
2. **User names an existing project** → `railway link`
3. **Directory name matches existing project** → Ask: link existing or create new?
4. **No matching projects** → `railway init`

### Create New Project

```bash
railway init -n <name>
```

Options:
- `-n, --name` — Project name
- `-w, --workspace` — Workspace name or ID (required if multiple workspaces)

#### Multiple Workspaces

Get workspace IDs from:
```bash
railway whoami --json
```

The `workspaces` array contains `{ id, name }` for each workspace.

### Link Existing Project

```bash
railway link -p <project>
```

Options:
- `-p, --project` — Project name or ID
- `-e, --environment` — Environment (default: production)
- `-s, --service` — Service to link
- `-t, --team` — Team/workspace

### Create Service

```bash
railway add --service <name>
```

**For GitHub repo sources**: Create empty service, then configure source via `environment edit`:

1. `railway add --service my-api`
2. Configure `source.repo` and `source.branch` via environment edit
3. Apply changes to trigger deployment

Reference [railpack.md](references/railpack.md) for build configuration.
Reference [monorepo.md](references/monorepo.md) for monorepo patterns.

---

## Deploy

Deploy code from the current directory using `railway up`.

### Modes

**Detach Mode (default)** — Starts deploy and returns immediately:
```bash
railway up --detach
```

**CI Mode** — Streams build logs until complete:
```bash
railway up --ci
```

Use CI mode when user says "deploy and watch", "deploy and fix issues", or is debugging build failures.

### Deploy Specific Service

```bash
railway up --detach --service backend
```

### Deploy to Unlinked Project

```bash
railway up --project <project-id> --environment production --detach
```

Requires both `--project` and `--environment` flags.

### CLI Options

| Flag | Description |
|------|-------------|
| `-d, --detach` | Don't attach to logs (default) |
| `-c, --ci` | Stream build logs, exit when done |
| `-s, --service <NAME>` | Target service |
| `-e, --environment <NAME>` | Target environment |
| `-p, --project <ID>` | Target project (requires --environment) |
| `[PATH]` | Path to deploy (defaults to cwd) |

### After Deploy

**Detach mode**: Use `railway deployment list` and `railway logs` to check status.

**CI mode**: Build logs stream inline. If build fails, the error is in the output.
Do NOT run `railway logs --build` after CI mode — logs already streamed.

---

## Configuration

Read and edit Railway environment configuration.

### Read Configuration

```bash
railway environment config --json
```

Returns: source (repo/image), build settings, deploy settings, variables per service.

### Get Rendered Variables

`environment config` returns unrendered variables (templates like `${{shared.DOMAIN}}`).

For rendered (resolved) values:
```bash
railway variables --json
# Or for specific service:
railway variables --service <name> --json
```

### Edit Configuration

Pass a JSON patch:
```bash
railway environment edit --json <<< '<json-patch>'
```

With commit message:
```bash
railway environment edit -m "description" --json <<< '<json-patch>'
```

### Examples

**Set build command:**
```bash
railway environment edit --json <<< '{"services":{"SERVICE_ID":{"build":{"buildCommand":"npm run build"}}}}'
```

**Set start command:**
```bash
railway environment edit --json <<< '{"services":{"SERVICE_ID":{"deploy":{"startCommand":"npm start"}}}}'
```

**Add variable:**
```bash
railway environment edit -m "add API_KEY" --json <<< '{"services":{"SERVICE_ID":{"variables":{"API_KEY":{"value":"secret"}}}}}'
```

**Delete variable:**
```bash
railway environment edit --json <<< '{"services":{"SERVICE_ID":{"variables":{"OLD_VAR":null}}}}'
```

**Set replicas:**
```bash
railway environment edit --json <<< '{"services":{"SERVICE_ID":{"deploy":{"multiRegionConfig":{"us-west2":{"numReplicas":3}}}}}}'
```

**Add shared variable:**
```bash
railway environment edit --json <<< '{"sharedVariables":{"DATABASE_URL":{"value":"postgres://..."}}}'
```

**Delete service:**
```bash
railway environment edit --json <<< '{"services":{"SERVICE_ID":{"isDeleted":true}}}'
```

### Get Service ID

```bash
railway status --json
```

Extract `service.id` from response. Or get all service IDs:
```bash
railway environment config --json | jq '.services | keys'
```

Map IDs to names via `railway status --json` — the `project.services` array contains `{ id, name }`.

For complete field reference, see [environment-config.md](references/environment-config.md).
For variable syntax, see [variables.md](references/variables.md).

### Create Environment

```bash
railway environment new <name>
```

Duplicate existing:
```bash
railway environment new staging --duplicate production
```

### Switch Environment

```bash
railway environment <name>
```

---

## Databases

Add official Railway database services.

### Available Databases

| Database | Template Code |
|----------|---------------|
| PostgreSQL | `postgres` |
| Redis | `redis` |
| MySQL | `mysql` |
| MongoDB | `mongodb` |

### Check for Existing Databases

Before creating, check if one exists via `railway environment config --json`.

Check `source.image` for:
- `ghcr.io/railway/postgres*` or `postgres:*` → Postgres
- `ghcr.io/railway/redis*` or `redis:*` → Redis
- `ghcr.io/railway/mysql*` or `mysql:*` → MySQL
- `ghcr.io/railway/mongo*` or `mongo:*` → MongoDB

### Adding a Database

Via CLI:
```bash
railway add --database postgres
```

Or via GraphQL API for more control:

**1. Get context:**
```bash
railway status --json
```

**2. Get workspace ID:**
```bash
scripts/railway-api.sh \
  'query { project(id: "PROJECT_ID") { workspaceId } }' '{}'
```

**3. Fetch template:**
```bash
scripts/railway-api.sh \
  'query { template(code: "postgres") { id serializedConfig } }' '{}'
```

**4. Deploy template:**
```bash
scripts/railway-api.sh \
  'mutation deploy($input: TemplateDeployV2Input!) {
    templateDeployV2(input: $input) { projectId workflowId }
  }' \
  '{"input": {"templateId": "...", "serializedConfig": {...}, "projectId": "...", "environmentId": "...", "workspaceId": "..."}}'
```

### Connecting to the Database

Use reference variables. For complete syntax, see [variables.md](references/variables.md).

**Backend services (private network):**

| Database | Variable Reference |
|----------|-------------------|
| PostgreSQL | `${{Postgres.DATABASE_URL}}` |
| Redis | `${{Redis.REDIS_URL}}` |
| MySQL | `${{MySQL.MYSQL_URL}}` |
| MongoDB | `${{MongoDB.MONGO_URL}}` |

**Example — connect backend to Postgres:**
```bash
railway environment edit --json <<< '{"services":{"BACKEND_ID":{"variables":{"DATABASE_URL":{"value":"${{Postgres.DATABASE_URL}}"}}}}}'
```

**Frontend note:** Frontends run in browser and can't access private network. Use public URLs or go through a backend API.

---

## Domains

Add, view, or remove domains.

### Add Railway Domain

Generate a railway-provided domain (max 1 per service):
```bash
railway domain --json
```

For specific service:
```bash
railway domain --json --service backend
```

### Add Custom Domain

```bash
railway domain example.com --json
```

Returns required DNS records. Tell user to add these to their DNS provider.

### Read Current Domains

```bash
railway environment config --json
```

Domains are in `config.services.<serviceId>.networking`:
- `serviceDomains` — Railway-provided domains
- `customDomains` — User-provided domains

### Remove Domain

Via `environment edit`:

**Remove custom domain:**
```json
{"services":{"<serviceId>":{"networking":{"customDomains":{"<domainId>":null}}}}}
```

**Remove railway domain:**
```json
{"services":{"<serviceId>":{"networking":{"serviceDomains":{"<domainId>":null}}}}}
```

### CLI Options

| Flag | Description |
|------|-------------|
| `[DOMAIN]` | Custom domain (omit for railway domain) |
| `-p, --port <PORT>` | Port to connect |
| `-s, --service <NAME>` | Target service |
| `--json` | JSON output |

---

## Monitoring

### Check Status

```bash
railway status --json
```

Present:
- **Project**: name and workspace
- **Environment**: current environment
- **Services**: list with deployment status
- **Active Deployments**: any in-progress (from `activeDeployments` field)
- **Domains**: configured domains

### Service Status

```bash
railway service status --json
```

### Deployment History

```bash
railway deployment list --limit 10 --json
```

### View Logs

**Deploy logs:**
```bash
railway logs --lines 100 --json
```

**Build logs:**
```bash
railway logs --build --lines 100 --json
```

**Latest deployment (including failed):**
```bash
railway logs --latest --lines 100 --json
```

**Filter logs:**
```bash
railway logs --lines 50 --filter "@level:error" --json
railway logs --lines 50 --filter "connection refused" --json
```

**Time-based:**
```bash
railway logs --since 1h --lines 100 --json
railway logs --since 30m --until 10m --lines 100 --json
```

**Specific deployment:**
```bash
railway logs <deployment-id> --lines 100 --json
railway logs --build <deployment-id> --lines 100 --json
```

### Redeploy

```bash
railway redeploy --service <name> -y
```

### Restart (no rebuild)

```bash
railway restart --service <name> -y
```

### Remove Deployment

Takes down current deployment (service remains):
```bash
railway down -y
railway down --service web -y
```

This does NOT delete the service. To delete a service, use `environment edit` with `isDeleted: true`.

---

## Error Handling

### CLI Not Installed

```
Railway CLI not installed. Install with:
  npm install -g @railway/cli
or
  brew install railway
```

### Not Authenticated

```
Not logged in to Railway. Run: railway login
```

### No Project Linked

```
No Railway project linked to this directory.

To link an existing project: railway link
To create a new project: railway init
```

### No Service Linked

```
No service linked. Use --service flag or run `railway service` to select one.
```

### Service Not Found

```
Service "foo" not found in project. Available services: api, web, worker
```

### Command Not Found (`environment edit`)

```
Command not found. Upgrade CLI: railway upgrade
```

---

## References

- [railpack.md](references/railpack.md) — Framework detection, build configuration
- [monorepo.md](references/monorepo.md) — Monorepo patterns (root directory vs custom commands)
- [variables.md](references/variables.md) — Variable syntax, service wiring
- [environment-config.md](references/environment-config.md) — Full config schema
