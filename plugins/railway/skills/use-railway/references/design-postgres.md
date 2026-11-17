# Postgres design: schema, indexes, queries, migrations

Use this when writing or reviewing a Postgres schema, an index, a query, or a migration. To measure a live database first, use [analyze-db-postgres.md](analyze-db-postgres.md). For PITR, HA, and pooling commands, use [databases.md](databases.md).

Validate advice on the user's own data: run `EXPLAIN (ANALYZE, BUFFERS)` against a realistic copy before claiming an improvement. `ANALYZE` executes the statement, so wrap writes in `BEGIN; ... ROLLBACK;`.

## Schema and data types

- **Primary keys**: default to `bigint GENERATED ALWAYS AS IDENTITY`. It is compact, ordered, and avoids the legacy `serial` sequence-ownership quirks. Use `int` only when the table can never exceed ~2.1 billion rows.
- **UUID keys**: random v4 UUIDs spread inserts across the whole B-tree, which costs cache and WAL on large tables. When IDs must be generated outside the database or be non-guessable, prefer time-ordered UUIDv7 (`uuidv7()` is built in from Postgres 18; generate it in the application on older versions). Store it as `uuid`, never `text`.
- **Text**: `text` and `varchar(n)` perform the same. Use `text` plus a `CHECK (char_length(col) <= n)` when a limit is a business rule.
- **Time**: use `timestamptz`. `timestamp` without time zone silently drops the offset.
- **Money and exact values**: `numeric(p, s)` or integer minor units (cents). Never `float`/`double precision` or `money`.
- **JSON**: `jsonb`, not `json`. Promote fields that are filtered, joined, or constrained into real columns; JSON keys have no type checks or statistics by default.
- **Enums**: a `text` column with a `CHECK` constraint or a lookup table is easier to evolve than `CREATE TYPE ... AS ENUM` (values cannot be removed from an enum).
- **Constraints**: declare `NOT NULL`, `UNIQUE`, `CHECK`, and foreign keys. They document intent and let the planner make better choices.
- **Foreign keys**: Postgres indexes the referenced key but **not** the referencing column. Index every FK column used in joins or in `ON DELETE` cascades, or deletes on the parent scan the child.

## Indexing

- **Composite order**: equality columns first, then the column used for sorting or range. `(tenant_id, created_at)` serves `WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 50`; `(created_at, tenant_id)` does not serve it well.
- **Leftmost prefix**: an index on `(a, b, c)` serves filters on `a`, `a, b`, and `a, b, c`. A filter on `b` alone usually needs its own index.
- **Covering**: `CREATE INDEX ... (customer_id) INCLUDE (status, total)` lets an index-only scan answer the query without touching the heap. Index-only scans depend on the visibility map, so tables with heavy churn benefit less until vacuum catches up.
- **Partial**: index only the rows queries touch, for example `CREATE INDEX ... ON jobs (run_at) WHERE status = 'pending'`. The query's `WHERE` must imply the index predicate.
- **Expression**: `CREATE INDEX ... ON users (lower(email))` serves `WHERE lower(email) = $1`. Wrapping an indexed column in a function or cast otherwise disables the plain index.
- **Other types**: GIN for `jsonb` containment, arrays, and full-text search; BRIN for very large append-only tables filtered by an insertion-correlated column such as `created_at`; `pg_trgm` GIN/GiST for `ILIKE '%term%'`.
- **Cost**: every index slows writes, uses memory, and can block HOT updates. Add indexes for measured queries, not for every column.

### Audit unused and duplicate indexes

```sql
-- Never-scanned indexes (excluding ones that enforce constraints)
SELECT s.schemaname, s.relname AS table, s.indexrelname AS index,
       pg_size_pretty(pg_relation_size(s.indexrelid)) AS size
FROM pg_stat_user_indexes s
JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE s.idx_scan = 0 AND NOT i.indisunique AND NOT i.indisprimary
ORDER BY pg_relation_size(s.indexrelid) DESC;

-- Non-unique indexes whose columns equal, or are a leading prefix of, another index of the same type
SELECT a.indexrelid::regclass AS redundant, b.indexrelid::regclass AS covered_by
FROM pg_index a
JOIN pg_index b ON b.indrelid = a.indrelid AND b.indexrelid <> a.indexrelid
JOIN pg_class ia ON ia.oid = a.indexrelid
JOIN pg_class ib ON ib.oid = b.indexrelid AND ib.relam = ia.relam
WHERE NOT a.indisunique
  AND a.indpred IS NULL AND b.indpred IS NULL
  AND a.indexprs IS NULL AND b.indexprs IS NULL
  AND (b.indkey::text LIKE a.indkey::text || ' %'
       OR (b.indkey::text = a.indkey::text
           AND (b.indisunique OR a.indexrelid > b.indexrelid)));
```

Treat the second query's rows as candidates: confirm with `\d table` that operator classes, collations, and `INCLUDE` columns match before dropping. Scan counters are per server and reset with `pg_stat_reset()` or a stats reset; on an HA cluster each replica keeps its own. Check how long stats have accumulated (`stats_reset` in `pg_stat_database`) before calling an index unused, and drop with `DROP INDEX CONCURRENTLY`.

## Query patterns

- **N+1**: replace a per-row lookup loop with one query: a join, `WHERE id = ANY($1)`, or the ORM's eager-loading option. Look for repeated identical statements in `pg_stat_statements` with very high `calls`.
- **Pagination**: `OFFSET` reads and discards every skipped row. Use keyset pagination on an indexed, unique ordering: `WHERE (created_at, id) < ($1, $2) ORDER BY created_at DESC, id DESC LIMIT 50`.
- **Sargable predicates**: compare the bare column to a value. `WHERE created_at >= $1 AND created_at < $2` uses an index; `WHERE date(created_at) = $1` does not unless an expression index exists. Match parameter types to column types to avoid implicit casts.
- **Select what you need**: avoid `SELECT *` on wide tables; it defeats index-only scans and drags TOASTed columns over the network.
- **Batching**: insert with multi-row `VALUES` or `COPY`; update or delete large sets in bounded batches (for example 1,000 to 10,000 rows by key range) with commits in between, so locks and WAL stay small and replicas keep up.
- **Counting**: exact `count(*)` on a large table is a full scan. Use `pg_class.reltuples` for estimates when exactness is not required.

## Transactions and locking

- Keep transactions short and never wait on user input or network calls inside one. A session left `idle in transaction` holds locks and blocks vacuum cleanup; set `idle_in_transaction_session_timeout` for application roles.
- Default isolation is `READ COMMITTED`. For read-modify-write, use `SELECT ... FOR UPDATE`, an atomic `UPDATE ... SET n = n + 1`, or `SERIALIZABLE` with retry on serialization failures (SQLSTATE `40001`).
- Work queues: `SELECT ... FOR UPDATE SKIP LOCKED LIMIT n` lets workers claim rows without blocking each other.
- Deadlocks (`40P01`) come from lock-order differences. Touch rows in a consistent order (for example sorted by primary key) and retry the transaction.

## Safe migrations

Most `ALTER TABLE` forms take an `ACCESS EXCLUSIVE` lock. The lock itself may be brief, but while it waits behind a long query, every later query on that table queues behind it. Guard every DDL migration:

```sql
SET lock_timeout = '5s';        -- fail fast instead of stalling traffic; retry later
SET statement_timeout = '15min';
```

- **Indexes**: `CREATE INDEX CONCURRENTLY` (and `DROP INDEX CONCURRENTLY`) avoid blocking writes. They cannot run inside a transaction block, so disable the migration tool's wrapping transaction for that step. A failed concurrent build leaves an `INVALID` index; drop it and retry.
- **Add column**: adding a nullable column, or one with a constant default (Postgres 11+), is metadata-only. A volatile default such as `random()` rewrites the table.
- **NOT NULL on an existing column**: add `CHECK (col IS NOT NULL) NOT VALID`, then `VALIDATE CONSTRAINT` (takes a weaker lock), then `SET NOT NULL` (Postgres 12+ uses the validated check to skip the scan), then drop the check.
- **Foreign keys and checks**: add with `NOT VALID`, then `VALIDATE CONSTRAINT` in a separate statement.
- **Type changes and renames**: most type changes rewrite the table. Use expand and contract: add the new column, dual-write, backfill in batches, switch reads, then drop the old column in a later deploy.
- **Backfills**: run as batched updates outside the DDL transaction, not as one giant `UPDATE`.

## On Railway

- **Connect**: `railway connect <service>` opens `psql`; `railway connect <service> --tunnel-only` holds a tunnel for GUI tools.
- **Pooling**: add PgBouncer when many short-lived connections (serverless, many replicas of an app) exhaust `max_connections`. Transaction mode is the default; it does not support session features such as `LISTEN/NOTIFY`, advisory locks, or `SET` across statements. Run migrations, `CREATE INDEX CONCURRENTLY`, and session-scoped work over `DATABASE_UNPOOLED_URL`. Docs: [PostgreSQL connection pooling](https://docs.railway.com/databases/postgresql-pgbouncer).
- **High availability**: convert to HA when the app cannot tolerate a single-node outage. Clients connect through HAProxy, which routes to the current primary; active connections drop during a failover, so the application must reconnect and retry. Docs: [PostgreSQL High Availability](https://docs.railway.com/databases/postgresql-ha).
- **Recovery**: enable point-in-time recovery before risky migrations, or take a named backup (`railway postgres pitr backup create --name pre-migration`). Docs: [Point-in-Time Recovery](https://docs.railway.com/volumes/point-in-time-recovery), [Backups](https://docs.railway.com/volumes/backups), [Back up and restore Postgres](https://docs.railway.com/guides/postgres-backups-restores).

## Validated against

- PostgreSQL documentation: CREATE INDEX (CONCURRENTLY, INCLUDE, partial and expression indexes), ALTER TABLE (NOT VALID, VALIDATE CONSTRAINT, SET NOT NULL), explicit locking, `pg_stat_user_indexes`, `uuidv7()` (Postgres 18)
- Railway docs: [PostgreSQL](https://docs.railway.com/databases/postgresql), [PostgreSQL HA](https://docs.railway.com/databases/postgresql-ha), [PgBouncer](https://docs.railway.com/databases/postgresql-pgbouncer), [PITR](https://docs.railway.com/volumes/point-in-time-recovery), [Backups](https://docs.railway.com/volumes/backups), [`railway postgres`](https://docs.railway.com/cli/postgres), [`railway connect`](https://docs.railway.com/cli/connect)
