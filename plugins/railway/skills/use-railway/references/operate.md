# Operate

Check health, read logs, query metrics, and troubleshoot failures.

## Health snapshot

Start broad, then narrow:

```bash
railway status --json                                    # linked context
railway service list --json                              # services in current environment
railway deployment list --limit 10 --json                # recent deployments
```

Deployment statuses: `SUCCESS`, `BUILDING`, `DEPLOYING`, `FAILED`, `CRASHED`, `REMOVED`.

For projects with buckets, include bucket status:

```bash
railway bucket list --json                                       # buckets in current environment
railway bucket info --bucket <name> --json                       # storage size, object count, region
```

If everything looks healthy, return a summary and stop. If something is degraded or failing, continue to log inspection.

## Logs

### Recent logs

```bash
railway logs --service <service> --lines 200 --json              # runtime logs
railway logs --service <service> --build --lines 200 --json      # build logs
railway logs --latest --lines 200 --json                         # latest deployment
```

In an interactive terminal, `railway logs` streams indefinitely when no bounding flags are given. Always use `--lines`, `--since`, or `--until` to get a bounded fetch for agent workflows.

### Time-bounded queries

```bash
railway logs --service <service> --since 1h --lines 400 --json
railway logs --service <service> --since 30m --until 10m --lines 400 --json
```

### Filtered queries

Use `--filter` to narrow logs without scanning everything manually:

```bash
railway logs --service <service> --lines 200 --filter "@level:error" --json
railway logs --service <service> --lines 200 --filter "@level:warn AND timeout" --json
railway logs --service <service> --lines 200 --filter "connection refused" --json
```

Filter syntax supports text search (`"error message"`), attribute filters (`@level:error`, `@level:warn`), and boolean operators (`AND`, `OR`, `-` for negation). Full syntax: https://docs.railway.com/guides/logs

### Scoped by environment

```bash
railway logs --service <service> --environment <env> --lines 200 --json
```

### HTTP logs

Use HTTP logs when a service responds with errors, latency spikes, or routing problems:

```bash
railway logs --service <service> --http --status ">=400" --lines 100 --json
railway logs --service <service> --http --method POST --path /api/users --lines 100 --json
railway logs --service <service> --http --request-id <request-id> --lines 20 --json
railway logs --service <service> --http --filter "@totalDuration:>=1000" --lines 100 --json
```

HTTP filter fields include `@method`, `@path`, `@host`, `@requestId`, `@srcIp`, `@edgeRegion`, `@httpStatus`, `@totalDuration`, `@responseTime`, `@txBytes`, and `@rxBytes`.

## Metrics

Use `railway metrics` for resource and HTTP metrics. It summarizes CPU, memory, network, volume, and HTTP data for the linked service by default.

```bash
railway metrics --service <service> --since 1h --json
railway metrics --service <service> --since 6h --cpu --memory --json
railway metrics --service <service> --http --method POST --path /api/users --json
railway metrics --all --environment production --json
```

Use `--raw` for time-series data points:

```bash
railway metrics --service <service> --raw --cpu --json
```

Metric flags can be combined: `--cpu`, `--memory`, `--network`, `--volume`, and `--http`. Use `--watch` only in an interactive terminal; it opens a live TUI and conflicts with `--json` and `--raw`.

For custom grouping or measurements the CLI doesn't expose, use the GraphQL fallback in [request.md](request.md).

## SSH

Use SSH when logs and metrics don't expose enough state and the user needs shell-level inspection inside a running service.

```bash
railway ssh --service <service> --environment <env>
railway ssh --service <service> --environment <env> -- "printenv | sort"
railway ssh --service <service> --environment <env> --session railway-debug
railway ssh --service <service> --environment <env> --identity-file ~/.ssh/id_ed25519_railway
```

Manage Railway SSH keys with:

```bash
railway ssh keys list
railway ssh keys add --key ~/.ssh/id_ed25519.pub --name <key-name>
railway ssh keys github
railway ssh keys remove <key-id> --2fa-code <code>
```

Workspace-owned keys use `--workspace <workspace-id>` and require workspace Admin access. SSH key management doesn't work with project tokens (`RAILWAY_TOKEN`); use `railway login` or a workspace-scoped `RAILWAY_API_TOKEN`.

## Database inspection

For database-level metrics and introspection, use the analysis scripts. `railway metrics` can provide infrastructure metrics and supported database summaries, while the scripts provide deeper engine-level analysis. See [analyze-db.md](analyze-db.md) for comprehensive database analysis including:

- Deep Postgres analysis (pg_stat_statements, vacuum health, index health, cache hit ratios)
- HA cluster checks (Patroni, etcd, HAProxy)
- Redis, MySQL, and MongoDB introspection
- Combined analysis via `scripts/analyze-<type>.py` (postgres, mysql, redis, mongo)

## Failure triage

When something is broken, classify the failure first. The fix depends on the class.

### Build failures

The service failed to build. Look at build logs:

```bash
railway logs --latest --build --lines 400 --json
```

Common causes and fixes:
- **Missing dependencies**: check lockfiles, verify package manager detection
- **Wrong build command**: override with `railway environment edit --service-config <service> build.buildCommand "<command>"`
- **Builder mismatch**: switch builders with `railway environment edit --service-config <service> build.builder RAILPACK`
- **Wrong root directory** (monorepo): set `source.rootDirectory` to the correct package path

### Runtime failures

The build succeeded but the service crashes or misbehaves:

```bash
railway logs --latest --lines 400 --json
railway logs --service <service> --since 1h --lines 400 --json
```

Common causes and fixes:
- **Bad start command**: override with `railway environment edit --service-config <service> deploy.startCommand "<command>"`
- **Missing runtime variable**: check `railway variable list --service <service> --json` and set missing values
- **Port mismatch**: the service must listen on `$PORT` (Railway injects this). Verify with logs.
- **Upstream dependency down**: check other services' status and logs

### Config-driven failures

Something worked before and broke after a config change:

```bash
railway environment config --json
railway variable list --service <service> --json
```

Compare the config against expected values. Look for changes that may have introduced the regression.

### Networking failures

Domain returns errors, or service-to-service calls fail:

```bash
railway domain --service <service> --json
railway logs --service <service> --lines 200 --json
railway logs --service <service> --http --status ">=400" --lines 100 --json
```

Check: target port matches what the service listens on, domain status is healthy, private domain variable references are correct.

## Recovery

After identifying the cause, fix and verify:

```bash
# Fix (examples)
railway environment edit --service-config <service> deploy.startCommand "<correct-command>"
railway variable set MISSING_VAR=value --service <service>

# Redeploy
railway redeploy --service <service> --yes

# Verify
railway service status --service <service> --json
railway logs --service <service> --lines 200 --json
```

Always verify after fixing. Don't assume the redeploy succeeded.

## Troubleshoot common blockers

- **Unlinked context**: `railway link --project <id-or-name>`
- **Missing service scope for logs**: pass `--service` and `--environment` explicitly
- **No deployments found**: the service exists but has never deployed, create an initial deploy first
- **Metrics return empty**: check the time window, service scope, and whether the service has active deployments
- **Config patch type error**: check the typed paths in [configure.md](configure.md), for example, `numReplicas` is an integer, not a string

## Validated against

- Docs: [status.md](https://docs.railway.com/cli/status), [service.md](https://docs.railway.com/cli/service), [logs.md](https://docs.railway.com/cli/logs), [metrics.md](https://docs.railway.com/cli/metrics), [ssh.md](https://docs.railway.com/cli/ssh), [observability/logs.md](https://docs.railway.com/observability/logs), [observability/metrics.md](https://docs.railway.com/observability/metrics)
- CLI source: [status.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/status.rs), [service.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/service.rs), [logs.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/logs.rs), [metrics.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/metrics.rs), [ssh/mod.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/ssh/mod.rs), [deployment.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/deployment.rs), [redeploy.rs](https://github.com/railwayapp/cli/blob/v4.58.0/src/commands/redeploy.rs)
