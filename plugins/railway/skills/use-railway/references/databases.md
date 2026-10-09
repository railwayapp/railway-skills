# Database operations

Use native CLI commands for database recovery, high availability, and connection pooling. Use [analyze-db.md](analyze-db.md) for performance analysis, [setup.md](setup.md) to create a database or connect a local client, and the design references ([Postgres](design-postgres.md), [MySQL](design-mysql.md), [Redis](design-redis.md), [MongoDB](design-mongo.md)) for schema, index, query, and migration guidance.

## Choose the engine and scope

| Engine | Commands |
|---|---|
| Postgres | `railway postgres pitr`, `ha`, `pgbouncer`, `history` |
| MySQL | `railway mysql ha`, `history` |
| Redis | `railway redis ha`, `history` |

Postgres operations arrived in CLI 5.33; MySQL/Redis HA in 5.46. Use **5.47.1 or newer for HA mutations**: that release added the revert and scaling fixes (staged member changes, never deleting the acting primary) and `--remove-orphans`. MySQL/Redis do not expose PITR or PgBouncer commands. Availability and image eligibility also depend on Railway's engine templates; a command existing does not make every custom database image eligible.

All these command trees accept `--project`, `--environment`, `--service`, and `--json`. Resolve the database service and environment first, especially when the supplied URL points at a replica or proxy. Use explicit IDs for cross-project work:

```bash
railway postgres pitr status --project <project-id> --environment <env> --service <service> --json
railway postgres ha status --project <project-id> --environment <env> --service <service> --json
railway postgres pgbouncer status --project <project-id> --environment <env> --service <service> --json
railway mysql ha status --project <project-id> --environment <env> --service <service> --json
railway redis ha status --project <project-id> --environment <env> --service <service> --json
```

The following examples abbreviate scope to `--service`; retain the resolved project and environment in actual calls. Config-changing actions deploy by default. Where supported, `--no-deploy` commits config but defers its runtime effect until the affected services deploy; it is not a dry-run. Use it only when deployment is deliberately deferred. Add `--yes` only for a mutation whose scope and impact the user authorized, and only where the command supports it.

## Postgres point-in-time recovery

```bash
railway postgres pitr status --service <postgres> --json
railway postgres pitr enable --service <postgres>
railway postgres pitr disable --service <postgres>
railway postgres pitr progress --service <postgres> --json
railway postgres pitr progress --service <postgres> --watch
```

`enable`/`disable` recognize a standalone database or an HA cluster root. Standalone operations support `--no-deploy`; HA enable/disable runs a live rolling workflow. `progress`, `cancel`, and `clear` apply only to that HA workflow. Inspect progress before canceling a stuck workflow; clear a completed snapshot only when intended. Bound a watch process and report its last observed phase if it times out.

Status includes a best-effort SSH probe of archive coverage and archiver health. `unavailable` or unknown probe results do not mean backups are disabled or healthy. Resolve SSH reachability or report the missing evidence.

To restore to a separate service:

```bash
railway postgres pitr restore --service <postgres> --at 2026-09-04T10:00:00Z --new-service-name postgres-restored
```

Use an explicit UTC timestamp to avoid local-time ambiguity. Relative offsets such as `30m` are also accepted. Check available coverage first, then verify the restored service's deployment and data before changing application connection variables. `--source-repo-path` selects an archive history when needed. Creating a restored service does not itself switch application traffic.

### Backups and schedules

```bash
railway postgres pitr backup list --service <postgres> --json
railway postgres pitr backup create --service <postgres> --name pre-migration
railway postgres pitr backup lock <backup-id> --service <postgres>
railway postgres pitr schedule list --service <postgres> --json
railway postgres pitr schedule set --daily --weekly --service <postgres>
railway postgres pitr backup restore <backup-id> --service <postgres>
railway postgres pitr backup delete <backup-id> --service <postgres>
```

`backup restore` overwrites the current data; it is different from `pitr restore`, which creates a new service. In-place backup restore on an HA cluster is rejected because replicas would diverge; use the dashboard workflow that reseeds replicas. Do not bypass the guard by restoring the root volume manually. `backup lock` keeps a backup indefinitely. `schedule set --none` removes automatic schedules while keeping existing backups. Verify the backup ID, target, and destructive impact before restore/delete.

## High availability

```bash
railway postgres ha convert --service <postgres> --replicas 2 --coordinators 3 --edge 1
railway postgres ha scale --service <postgres> --replicas 3
railway postgres ha switchover --service <postgres> --to <replica-name-or-id>
railway postgres ha revert --service <postgres>
railway mysql ha convert --service <mysql> --replicas 2
railway mysql ha scale --service <mysql> --replicas 4
railway redis ha convert --service <redis> --replicas 2
railway redis ha switchover --service <redis> --to <replica-name-or-id>
```

`--replicas` counts replicas **excluding the primary**. Omitted conversion counts preserve the template defaults. MySQL and Redis carry consensus on their data nodes: total data nodes must be odd and at least three, so pass an even replica count such as 2 or 4. These conversions require a source image tagged with an exact major.minor version. Separate `--coordinators` applies only to templates with that tier; its count must be odd. Follow the template's reported constraints rather than copying a Postgres topology to another engine.

Before scaling or switching, inspect live member roles and probe errors. Switchover requires a reachable eligible target and may briefly interrupt connections. After conversion/scale/switchover, reread HA status and verify primary role, replica health, and application connectivity; a committed config alone is not evidence that replication is healthy.

Revert returns the database to standalone and removes cluster members. Current CLI fixes protect the acting primary and retain the independent PgBouncer pooler. `--remove-orphans` is a separate cleanup opt-in: orphaned members may no longer identify which same-engine cluster owned them. Do not add it merely to make a retry succeed. If an operation fails midway, inspect current config, live roles, and history before retrying or cleaning up.

## Postgres connection pooling

```bash
railway postgres pgbouncer status --service <postgres> --json
railway postgres pgbouncer add --service <postgres> --pool-mode transaction
railway postgres pgbouncer configure --service <postgres> --max-client-conn 200
railway postgres pgbouncer scale --service <postgres> --replicas 2
railway postgres pgbouncer remove --service <postgres>
```

Pooling works with standalone Postgres and HA roots. Modes are `transaction`, `session`, and `statement`; choose based on the application's session/transaction requirements. Check utilization and existing limits before changing connection counts. Verify the pooler's deployment and connection endpoint before wiring the app to it; removing the pooler requires restoring a suitable application connection path.

## Verify and investigate

```bash
railway postgres history --service <postgres> --limit 10 --json
railway mysql history --service <mysql> --limit 10 --json
railway redis history --service <redis> --limit 10 --json
```

History is a **local** operation trail, not a complete account audit log. Pair it with fresh native status, scoped deployment status, and logs. Do not infer that no changes happened just because this machine has no history. Follow [operate.md](operate.md) for deployment/log triage and [analyze-db.md](analyze-db.md) for deeper queries.

## Validated against

- Docs: [Postgres CLI](https://docs.railway.com/cli/postgres)
- CLI source (v5.49.1): [postgres.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/postgres.rs), [mysql.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/mysql.rs), [redis.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/redis.rs), [pitr.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/database/pitr.rs), [ha.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/database/ha.rs), [pool.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/database/pool.rs), [ops_log.rs](https://github.com/railwayapp/cli/blob/v5.49.1/src/commands/database/ops_log.rs)
