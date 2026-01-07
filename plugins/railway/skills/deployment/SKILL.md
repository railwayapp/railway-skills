---
name: deployment
description: Manage Railway deployments. Use when user says "remove deploy", "take down", "stop deployment", "railway down", "redeploy", "restart", "list deployments", "show logs", "check errors", or "debug". NOT for deleting services - this removes/manages deployments only.
allowed-tools: Bash(railway:*)
---

# Deployment Management

Manage existing Railway deployments: list, view logs, redeploy, or remove.

**Important:** "Remove deployment" (`railway down`) stops the current deployment but keeps the service. To delete a service entirely, use the `environment` skill with `isDeleted: true`.

## When to Use

- User says "remove deploy", "take down service", "stop deployment", "railway down"
- User wants to "redeploy", "restart the service", "restart deployment"
- User asks to "list deployments", "show deployment history", "deployment status"
- User asks to "see logs", "show logs", "check errors", "debug issues"

## List Deployments

```bash
railway deployment list --limit 10 --json
```

Shows deployment IDs, statuses, and metadata. Use to find specific deployment IDs for logs or debugging.

### Specify Service

```bash
railway deployment list --service backend --limit 10 --json
```

## View Logs

### Deploy Logs

```bash
railway logs --lines 100 --json
```

In non-interactive mode, streaming is auto-disabled and CLI fetches logs then exits.

### Build Logs

```bash
railway logs --build --lines 100 --json
```

For debugging build failures or viewing build output.

### Logs for Failed/In-Progress Deployments

By default `railway logs` shows the last successful deployment. Use `--latest` for current:

```bash
railway logs --latest --lines 100 --json
```

### Filter Logs

```bash
# Errors only
railway logs --lines 50 --filter "@level:error" --json

# Text search
railway logs --lines 50 --filter "connection refused" --json

# Combined
railway logs --lines 50 --filter "@level:error AND timeout" --json
```

### Logs from Specific Deployment

```bash
railway logs <deployment-id> --lines 100 --json
```

Get the deployment ID from `railway deployment list`.

## Redeploy

Redeploy the most recent deployment:

```bash
railway redeploy --service <name> -y
```

The `-y` flag skips confirmation. Useful when:
- Config changed via environment skill
- Need to restart without new code
- Previous deploy succeeded but service misbehaving

## Remove Deployment

Takes down the current deployment. The service remains but has no running deployment.

```bash
# Remove deployment for linked service
railway down -y

# Remove deployment for specific service
railway down --service web -y
railway down --service api -y
```

This is what users mean when they say "remove deploy", "take down", or "stop the deployment".

**Note:** This does NOT delete the service. To delete a service entirely, use the `environment` skill with `isDeleted: true`.

## CLI Options

### deployment list

| Flag | Description |
|------|-------------|
| `-s, --service <NAME>` | Service name or ID |
| `-e, --environment <NAME>` | Environment name or ID |
| `--limit <N>` | Max deployments (default 20, max 1000) |
| `--json` | JSON output |

### logs

| Flag | Description |
|------|-------------|
| `-s, --service <NAME>` | Service name or ID |
| `-e, --environment <NAME>` | Environment name or ID |
| `-b, --build` | Show build logs |
| `-n, --lines <N>` | Number of lines (required) |
| `-f, --filter <QUERY>` | Filter using query syntax |
| `--latest` | Most recent deployment (even if failed) |
| `--json` | JSON output |
| `[DEPLOYMENT_ID]` | Specific deployment (optional) |

### redeploy

| Flag | Description |
|------|-------------|
| `-s, --service <NAME>` | Service name or ID |
| `-y, --yes` | Skip confirmation |

### down

| Flag | Description |
|------|-------------|
| `-s, --service <NAME>` | Service name or ID |
| `-e, --environment <NAME>` | Environment name or ID |
| `-y, --yes` | Skip confirmation |

## Presenting Logs

When showing logs:
- Include timestamps
- Highlight errors and warnings
- For build failures: show error and suggest fixes
- For runtime crashes: show stack trace context
- Summarize patterns (e.g., "15 timeout errors in last 100 logs")

## Composability

- **Push new code**: Use `deploy` skill
- **Check service status**: Use `status` skill
- **Fix config issues**: Use `environment` skill
- **Create new service**: Use `new` skill

## Error Handling

### No Service Linked
```
No service linked. Run `railway service` to select one.
```

### No Deployments Found
```
No deployments found. Deploy first with `railway up`.
```

### No Logs Found
Deployment may be too old (log retention limits) or service hasn't produced output.
