---
name: status
description: Check Railway project status. Use when user asks about Railway, deployments, services, environments, or before any Railway operation like deploying or updating services.
allowed-tools: Bash(railway:*), Bash(which:*), Bash(command:*)
---

# Railway Status

Check the current Railway project status for this directory.

## When to Use

- User asks about Railway status, project, services, or deployments
- User mentions deploying or pushing to Railway
- Before any Railway operation (deploy, update service, add variables)
- User asks about environments or domains

## Check Status

Run:
```bash
railway status --json
```

First verify CLI is installed:
```bash
command -v railway
```

## Handling Errors

### CLI Not Installed
If `command -v railway` fails:

> Railway CLI is not installed. Install with:
> ```
> npm install -g @railway/cli
> ```
> or
> ```
> brew install railway
> ```
> Then authenticate: `railway login`

### Not Authenticated
If `railway whoami` fails:

> Not logged in to Railway. Run:
> ```
> railway login
> ```

### No Project Linked
If status returns "No linked project":

> No Railway project linked to this directory.
>
> To link an existing project: `railway link`
> To create a new project: `railway init`

## Presenting Status

Parse the JSON and present:
- **Project**: name and workspace
- **Environment**: current environment (production, staging, etc.)
- **Services**: list with deployment status
- **Domains**: any configured domains

Example output format:
```
Project: my-app (workspace: my-team)
Environment: production

Services:
- web: deployed (https://my-app.up.railway.app)
- api: deployed
- postgres: running
```
