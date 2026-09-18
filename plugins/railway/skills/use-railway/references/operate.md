# Operate

Check health, read logs, query metrics, and troubleshoot failures.

## Health snapshot

Start broad, then narrow:

```bash
railway status --json                                    # linked context
railway status --project <project> --environment <env> --json
railway service list --json                              # services in current environment
railway deployment list --limit 10 --json                # recent deployments
railway deployment list --project <project> --environment <env> --service <service> --limit 10 --json
```

Use explicit `--project`, `--environment`, and `--service` when the user provided a URL or when the current directory may be linked to a different project.

Deployment statuses include `SUCCESS`, `QUEUED`, `INITIALIZING`, `WAITING`, `BUILDING`, `DEPLOYING`, `NEEDS_APPROVAL`, `FAILED`, `CRASHED`, `SLEEPING`, `SKIPPED`, `REMOVING`, and `REMOVED`.

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

Filter syntax supports text search (`"error message"`), attribute filters (`@level:error`, `@level:warn`), and boolean operators (`AND`, `OR`, `-` for negation). Full syntax: https://docs.railway.com/cli/logs

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

### Network flow logs

Use network flow logs for private networking, TCP proxy, outbound allowlist, or dropped-packet investigations. Use DNS query logs below for resolution results:

```bash
railway logs --service <service> --network --lines 100 --json
railway logs --service <service> --network --direction egress --protocol tcp --lines 100 --json
railway logs --service <service> --network --peer postgres --port 5432 --lines 100 --json
railway logs --service <service> --network --status dropped --lines 100 --json
railway logs --service <service> --network --filter "@peer_kind:internet @port:443" --lines 100 --json
```

Network flow logs are service-level, not deployment-level. Do not pass a deployment ID or `--latest` with `--network`.

Useful filters:

| Flag | Use for |
|---|---|
| `--protocol tcp|udp|icmp|icmpv6|unknown` | Layer 4 protocol |
| `--direction ingress|egress` | Traffic direction |
| `--peer <service|internet|dns|edge-proxy>` | Named peer or well-known peer |
| `--peer-kind service|internet|edge_proxy|local_dns|unknown` | Peer class |
| `--status ok|dropped` / `--dropped true` | Dropped traffic |
| `--port <port>` | Source or destination port |
| `--src`, `--dst`, `--host` | IP filters |
| `--drop-cause <cause>` | Drop reason |

### DNS query logs

CLI 5.29+ exposes DNS resolution results directly:

```bash
railway logs --service <service> --environment <env> --dns --lines 100 --json
railway logs --service <service> --dns --status failed --since 1h --lines 100 --json
railway logs --service <service> --dns --rcode NXDOMAIN --lines 100 --json
railway logs --service <service> --dns --qname backend.railway.internal --zone internal --lines 50 --json
railway logs --service <service> --dns --domain example.com --qtype AAAA --lines 100 --json
```

Use `--qname` for the full query name, `--domain` for domain filtering, `--qtype` for record type, `--rcode` for DNS response code, and `--zone internal|external` for lookup scope. `--status failed` finds failed resolutions. DNS logs are service-level and mutually exclusive with build, deployment, HTTP, and network modes; do not pass a deployment ID or `--latest`. Correlate failed lookups with runtime errors and network flows instead of treating a DNS failure as an application crash.

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

For latency or errors that span several services, or a request a user reported with an `x-railway-trace-id` header, use tracing instead of correlating logs by hand: see [tracing.md](tracing.md).

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

For native PITR/HA/PgBouncer status and operations, use [databases.md](databases.md). For billed usage and spending limits, use [usage.md](usage.md); infrastructure metrics are not a billing statement.

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
railway domain list --service <service> --json
railway domain status <domain> --service <service> --json
railway private-network status --service <service> --json
railway tcp-proxy list --service <service> --json
railway outbound-network status --service <service> --json
railway logs --service <service> --http --status ">=400" --lines 100 --json
railway logs --service <service> --network --status dropped --lines 100 --json
```

Check: target port matches what the service listens on, domain status is healthy, private domain variable references are correct, TCP proxy status is active, and outbound networking changes have been followed by the required redeploy.

### CDN and WAF incidents

For cache behavior, inspect both CLI settings and response headers:

```bash
railway cdn status --service <service> --json
railway logs --service <service> --http --status ">=400" --lines 100 --json
curl -I https://<domain>/<path>
curl https://<domain>/.railway/cdn-trace?json
```

`x-cache: HIT` means the request did not reach the service. `DYNAMIC` means the edge reached the service but did not cache the response. Check method, `Authorization`, `Set-Cookie`, `Cache-Control`, `Vary`, response size, and HTML caching mode.

For active traffic floods or unexpected `429` responses:

```bash
railway waf under-attack status --service <service> --json
railway logs --service <service> --http --status 429 --lines 100 --json
```

Under Attack Mode can block API clients and webhooks. If the service is API-only, disabling WAF may be the correct recovery after confirming with the user.

## Recovery

After identifying the cause, fix and verify:

```bash
# Fix (examples)
railway environment edit --service-config <service> deploy.startCommand "<correct-command>"
railway variable set MISSING_VAR=value --service <service>

# Redeploy
railway redeploy --service <service> --yes

# Verify
railway deployment list --service <service> --limit 5 --json
railway logs --service <service> --lines 200 --json
```

Always verify after fixing. Don't assume the redeploy succeeded.

## Troubleshoot common blockers

- **`OAUTH_INSUFFICIENT_GRANT` / resource access denied**: CLI 5.37.4+ distinguishes a live OAuth session without access from an expired login. Check the resource IDs, workspace membership, and integration grant scope; repeating the same login may retain the same insufficient grant. Reauthorize with the necessary access only when the user intends that scope.
- **Expired or invalid credentials**: follow the CLI's login/token-specific error. Transient refresh failures are not proof that access was revoked. Newer CLI versions refresh long-lived clients too; upgrade an old CLI before repeatedly reinstalling MCP to address stale authentication.
- **CI log stream failed**: on CLI 5.41+, the command falls back to status polling. Inspect the submitted deployment before retrying; a logging error alone is not a deployment failure.

- **Unlinked context**: `railway link --project <id-or-name>`
- **Missing service scope for logs**: pass `--service` and `--environment` explicitly
- **Wrong project in status or deploy polling**: pass `--project`, `--environment`, and `--service`; URL IDs beat local linked context
- **No deployments found**: the service exists but has never deployed, create an initial deploy first
- **Metrics return empty**: check the time window, service scope, and whether the service has active deployments
- **Config patch type error**: check the typed paths in [configure.md](configure.md), for example, `numReplicas` is an integer, not a string
- **No network flow logs**: confirm the time window and service scope; network logs are not tied to deployment IDs

## Validated against

- Docs: [status.md](https://docs.railway.com/cli/status), [service.md](https://docs.railway.com/cli/service), [logs.md](https://docs.railway.com/cli/logs), [metrics.md](https://docs.railway.com/cli/metrics), [ssh.md](https://docs.railway.com/cli/ssh), [cdn.md](https://docs.railway.com/cli/cdn), [waf.md](https://docs.railway.com/cli/waf), [observability/logs.md](https://docs.railway.com/observability/logs), [observability/metrics.md](https://docs.railway.com/observability/metrics), [observability/tracing.md](https://docs.railway.com/observability/tracing)
- CLI source: [status.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/status.rs), [service.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/service.rs), [logs.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/logs.rs), [metrics.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/metrics.rs), [ssh/mod.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/ssh/mod.rs), [deployment.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/deployment.rs), [redeploy.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/redeploy.rs), [cdn.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/cdn.rs), [waf.rs](https://github.com/railwayapp/cli/blob/v5.23.3/src/commands/waf.rs)
- Authentication and CI recovery (v5.49.1): [client.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/client.rs), [up.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/up.rs)
