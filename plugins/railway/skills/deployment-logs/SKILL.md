---
name: deployment-logs
description: View Railway deployment logs. Use when user asks to see logs, check errors, debug issues, or investigate service behavior.
---

# Deployment Logs

View build or deploy logs from Railway services.

## When to Use

- User asks to "see logs", "show logs", "check logs"
- Debugging build or deploy failures
- Investigating runtime errors or crashes
- Checking service behavior

## View Deploy Logs

```bash
railway logs --lines 100 --json
```

**Important:** Always use `--lines` to fetch a fixed number of logs. Without it,
the command streams indefinitely which doesn't work.

## View Build Logs

For build failures or to see build output:
```bash
railway logs --build --lines 100 --json
```

## Specify Service

Default is the linked service. To view logs from a different service:
```bash
railway logs --service backend --lines 100 --json
```

The `--service` flag accepts service name or ID. The CLI resolves names automatically.

## Filter Logs

Use `--filter` with Railway's query syntax:

```bash
# Errors only
railway logs --lines 50 --filter "@level:error" --json

# Warnings
railway logs --lines 50 --filter "@level:warn" --json

# Text search
railway logs --lines 50 --filter "connection refused" --json

# Combined
railway logs --lines 50 --filter "@level:error AND timeout" --json
```

## CLI Options

| Flag | Description |
|------|-------------|
| `-s, --service <NAME>` | Service name or ID (defaults to linked) |
| `-e, --environment <NAME>` | Environment name or ID (defaults to linked) |
| `-b, --build` | Show build logs |
| `-n, --lines <N>` | Number of lines to fetch (required) |
| `-f, --filter <QUERY>` | Filter using query syntax |
| `--json` | JSON output |
| `[DEPLOYMENT_ID]` | Specific deployment ID (optional) |

## Presenting Logs

When showing logs to the user:
- Include timestamps
- Highlight errors and warnings
- For build failures: show the error and suggest fixes
- For runtime crashes: show stack trace context
- Summarize patterns (e.g., "15 connection timeout errors in last 100 logs")

## Error Handling

### No Service Linked
```
No service linked. Run `railway service` to select one.
```

### No Deployments
```
No deployments found. Deploy first with `railway up`.
```

### No Logs Found
The deployment may be too old (logs have retention limits) or the service
hasn't produced output yet.
