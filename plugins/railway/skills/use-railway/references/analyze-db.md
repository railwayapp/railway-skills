# Database Analysis

## Your Role

You are a database performance expert. The script collects raw data - your job is to **think deeply** about what you see, identify root causes, correlate symptoms, and explain the "why" behind problems.

**Don't just report metrics. Analyze them.**

## Context: URL First, Never Trust CLI Linking

When a Railway URL is provided, **extract IDs directly from the URL**. Do NOT run `railway status --json` to discover context — it returns whatever project is locally linked, which is usually a different project.

```
https://railway.com/project/<PROJECT_ID>/service/<SERVICE_ID>?environmentId=<ENV_ID>
https://railway.com/project/<PROJECT_ID>/service/<SERVICE_ID>/database?environmentId=<ENV_ID>
```

With the project, service, and environment IDs from the URL, query the API for the service name and database type in a **single call**:

```bash
scripts/railway-api.sh \
  'query getServiceAndConfig($serviceId: String!, $environmentId: String!) {
    service(id: $serviceId) { name }
    environment(id: $environmentId) {
      config(decryptVariables: false)
    }
  }' \
  '{"serviceId": "<SERVICE_ID>", "environmentId": "<ENV_ID>"}'
```

From the response, get:
- **Service name**: `data.service.name`
- **Database image**: `data.environment.config.services.<SERVICE_ID>.source.image`

Then match the image to the database type:

| Image pattern | Database Type |
|--------------|---------------|
| `postgres*`, `ghcr.io/railway/postgres*` | PostgreSQL |
| `mysql*`, `ghcr.io/railway/mysql*` | MySQL |
| `redis*`, `ghcr.io/railway/redis*`, `railwayapp/redis*` | Redis |
| `mongo*`, `ghcr.io/railway/mongo*` | MongoDB |

If no URL is provided and you must discover context, then `railway status --json` is acceptable as a fallback.

## Database Type Detection and Script Selection

| Database Type | Script |
|---------------|--------|
| PostgreSQL | `scripts/analyze-db.py --type postgres` |
| MySQL | `scripts/analyze-mysql.py --type mysql` |
| Redis | `scripts/analyze-redis.py --type redis` |
| MongoDB | `scripts/analyze-mongo.py --type mongo` |

**All scripts share the same CLI interface:**
```bash
python3 scripts/analyze-<type>.py \
  --service <name> \
  --type <type> \
  --json \
  --project-id <project-id> \
  --environment-id <env-id> \
  --service-id <service-id>
```

Common options across all scripts:
- `--json` — JSON output for programmatic processing
- `--quiet` — Suppress progress messages
- `--skip-logs` — Skip log collection
- `--metrics-hours <N>` — Hours of metrics history (default: 24, max: 168)
- `--step <step>` — Debug individual collection steps (ssh-test, query, logs, metrics)

## Before You Analyze: Check Collection Status

**ALWAYS check `collection_status` and `errors[]` FIRST before interpreting any data.** The script collects data from multiple independent sources. Any of them can fail.

### Decision Table

| database_query | metrics_api | logs_api | Report Type |
|---------------|-------------|----------|-------------|
| success | success | success | Full analysis — use all sections |
| success | error | success | Full analysis — note missing infrastructure metrics |
| **error** | success | success | **Partial report** — only infrastructure metrics + log analysis. NO performance conclusions. |
| **error** | error | success | **Logs-only report** — state what logs show, note everything else failed. NO diagnosis. |
| **error** | **error** | **error** | **Collection failure** — report the errors, do not analyze. |

### When database_query failed

This means SSH could not reach the database or the query failed. You have NO connection stats, NO cache hit ratios, NO vacuum health, NO query performance data. All those fields will be null/empty.

**You MUST:**
1. State clearly: "Database introspection failed — SSH could not connect to the service"
2. Show the `collection_status` errors
3. Show only the data that DID succeed (metrics, logs)
4. Do NOT produce recommendations based on null metrics
5. Do NOT diagnose performance issues from logs alone

**Partial report template:**
```
Service: <name>
Status: Data collection partially failed

## Collection Status
| Source | Status |
|--------|--------|
| Database Query (SSH) | ERROR: <error from collection_status> |
| Metrics API | <status> |
| Logs API | <status> |

## Available Data
<Show metrics and log summary from sources that succeeded>

## What We Cannot Determine
<List what requires the database query: connection health, cache performance, vacuum health, query analysis, etc.>
```

## Output Structure: Data First, Actions Second

**Always present information in this order:**

### 1. Context Header
```
Service: <name> (<project> <environment>)
Status: <deployment health>, <RAM>, <disk used>
```

### 2. Consolidated Data Tables

Before any analysis, show the raw metrics in tables so the user sees their actual state:

**Configuration vs Recommended:**
| Parameter | Current | Recommended | Impact |
|-----------|---------|-------------|--------|
| shared_buffers | 128 MB | 1 GB | Why this matters |

**Table Health (if issues found):**
| Table | Dead Rows | Size | Dead % | Status |
|-------|-----------|------|--------|--------|
| Notification | 26,327 | 75 MB | 16.4% | Needs vacuum |

Only include tables with meaningful impact (see Vacuum Priority Matrix). Skip tiny tables even if they have high dead %.

**Cache Performance (if suboptimal):**
| Table | Cache Hit | Disk Reads | Size |
|-------|-----------|------------|------|
| Email | 6% | 1.19B | 1.7 GB |

**Connection Summary (if concerning):**
| Metric | Current | Max | Status |
|--------|---------|-----|--------|

**Slow Queries (top offenders from pg_stat_statements):**
| Query | Calls | Mean | Cache Hit | Temp Blocks | Issue |
|-------|-------|------|-----------|-------------|-------|
| Thread zone lookup | 105K | 1078ms | 99.7% | 0 | Complex nested EXISTS |
| Email ccFull join | 78K | 101ms | 47% | 0 | Scanning Email table |
| Thread pagination | 48K | 279ms | 98.8% | 39M | Spilling to disk |

Truncate query text to essential parts (tables, operations). Flag the specific issue.

**Logs & Active Issues:**
- Parse the `recent_logs` array (1000 lines of raw logs) - don't just check if empty
- Summarize: "Analyzed 1000 log lines: 3 errors (connection timeouts), 12 warnings (autovacuum), no critical issues"
- Show specific concerning log entries if found
- State if `long_running_queries` or `blocked_queries` had entries
- **Categorize log entries**: group by type (connection errors, slow queries, autovacuum activity, checkpoints, replication, crashes/restarts)
- **Count patterns**: "47 slow query warnings in 1000 lines = ~5% of all log output is slow query noise"
- **Quote actual log lines** for errors — don't just say "errors found", show the exact message so the user can search their codebase

### 3. Analysis

After showing the data, explain the chain of causation. Connect the dots between tables.

### 4. Recommended Actions

Group by urgency and restart requirements:
```
Immediate (no restart):
<SQL commands>

Short-term (requires restart):
<SQL commands>
```

### 5. Expected Outcomes

What metrics should change after fixes.

---

**Why this order matters:**
- Users can verify the data matches their understanding
- They see the full picture before being told what to do
- Actions have context - they know WHY each fix is recommended
- No valuable data is hidden in prose or omitted

## CRITICAL: Use the Actual Data

**NEVER fabricate or assume values.** The script outputs JSON with exact numbers. Before stating any metric:

1. **Read the actual JSON output** - Don't truncate or skim
2. **Quote the exact values** - e.g., `"max": 5000` not "100"
3. **Check what's present** - If `top_queries` has data, pg_stat_statements IS working
4. **Investigate outliers** - If `oldest_connection_sec` is high, check `oldest_connections` for details

Common errors to avoid:
- Saying "enable pg_stat_statements" when `pg_stat_statements_installed: true` and `top_queries` has data
- Misreporting connection usage (check `percent` field, not just `current`)
- Ignoring the `oldest_connections` details when flagging old connections
- Saying "746 GB of temp files on disk" when temp_bytes is cumulative since stats reset
- Marking tiny tables (< 10 MB) as "critical" for vacuum just because of high dead row percentage
- **Not parsing `recent_logs`** - always analyze the 1000 raw log lines, don't just report "no errors"
- Listing slow queries by total_time only without analyzing cache_hit_pct, temp_blks, and rows returned
- Dumping full ORM-generated SQL instead of summarizing the query pattern
- **Diagnosing performance issues from logs when all metrics are null** — logs show what happened, not how the database is performing
- **Treating startup/restart log entries as evidence of failure** — databases restart for many normal reasons (deploys, config changes, scaling)
- **Producing recommendations when all database metrics are null** — if `collection_status.database_query` is "error", you have no basis for tuning advice

## How to Think About Database Performance

### The Core Question

When you see a problem, ask: **What is the chain of causation?**

Example chain:
1. Cache hit is 89% (symptom)
2. Email table has 6% cache hit with 1.19B disk reads (deeper symptom)
3. Email table is 1.7GB, shared_buffers is 128MB (root cause)
4. The table is 13x larger than the buffer pool - it will NEVER fit in cache
5. Every query touching Email forces disk I/O

**This reasoning is what you provide. The script gives you the data points - you connect them.**

### Patterns to Look For

**Memory Starvation Pattern:**
- Low cache hit + large tables + small shared_buffers = working set doesn't fit
- High temp files + low work_mem = sorts/hashes spilling to disk
- These often occur together - both indicate the database needs more memory

**Important:** Temp file stats (`temp_files`, `temp_bytes`) are **cumulative since the last stats reset**, not current disk usage. When reporting, say "X GB written to temp files since stats reset" - not "X GB on disk right now".

**Vacuum Neglect Pattern:**
- High dead rows % + "never" vacuum timestamps = autovacuum isn't keeping up
- Multiple tables with >10% dead rows = systemic issue, not one-off
- High XID age + vacuum issues = potential wraparound emergency

**Important:** Consider **absolute impact**, not just percentage. A tiny table (< 10 MB) with 20% dead rows has negligible impact - vacuuming it reclaims almost nothing. Prioritize tables with BOTH high dead row counts (thousands+) AND meaningful size (tens of MB+). Don't mark small tables as "critical" just because of a high percentage.

**Missing Index Pattern:**
- High seq_scan count + 0 idx_scans on large tables = queries scanning full tables
- Low cache hit on specific tables + high seq_scans = indexes would help AND reduce I/O

**Connection Pressure Pattern:**
- High connection % + many idle connections = connection pooling needed
- Old connections (days) + idle_in_transaction = potential connection leaks or stuck transactions

### Slow Query Analysis — Go Deep

The `top_queries` array is the **most valuable data** for customers. This is where you can give the most actionable, specific advice. Don't skim it — analyze every query in the top 10-15 thoroughly.

#### Per-Query Fields and What Each Tells You

| Field | What It Means | How to Interpret |
|-------|---------------|------------------|
| `calls` | Number of times this query pattern executed | High calls × even small mean_ms = huge cumulative impact. A 5ms query called 10M times = 833 minutes of DB time |
| `total_min` | Total execution time in minutes | The primary sort key. This is the query's total footprint on the database |
| `mean_ms` | Average execution time per call | Compare with stddev — if stddev >> mean, the query has wildly variable performance |
| `min_ms` / `max_ms` | Fastest and slowest execution | A 2ms min with 30,000ms max means the query sometimes hits pathological cases (lock waits, cache misses, bloated tables) |
| `stddev_ms` | Standard deviation of execution time | High stddev = unpredictable. The query probably performs well when data is cached but terribly when it's not. This is often the query causing random user-visible latency spikes |
| `rows_per_call` | Average rows returned per execution | 0.01 rows/call means the query usually returns nothing — might be a polling pattern or existence check that could use EXISTS instead. 50,000 rows/call suggests missing pagination or bulk fetch |
| `mean_plan_ms` | Average planning time | If plan time is >5ms, the planner is spending significant time. Could indicate: too many partitions, complex joins needing better statistics (`ALTER TABLE SET STATISTICS`), or pg_catalog bloat |
| `cache_hit_pct` | % of blocks found in shared_buffers | <90% = query is constantly going to disk. Cross-reference with the table it touches in `cache_per_table` |
| `shared_blks_read` | Blocks read from disk (not cache) | This is the raw I/O cost. Each block = 8KB. 1M blocks read = 8GB of disk I/O |
| `shared_blks_dirtied` | Blocks this query modified | High dirtied blocks = write-heavy query. These blocks will need to be flushed to disk during checkpoints |
| `shared_blks_written` | Blocks this query had to flush to disk itself | Should be 0 in a healthy system. >0 means the query was forced to do its own I/O because shared_buffers was full of dirty pages — a sign of severe memory pressure |
| `temp_blks_read` / `temp_blks_written` | Blocks spilled to temp files | Any nonzero value means the query exceeded work_mem. Each block = 8KB. temp_blks_written of 1M = 8GB spilled to disk for sorts/hashes |
| `blk_read_time_ms` / `blk_write_time_ms` | Time spent on actual disk I/O (requires `track_io_timing`) | If available and high, this tells you exactly how much time was spent waiting on disk vs CPU. If 0, track_io_timing may be off |
| `wal_records` / `wal_bytes` | WAL generated by this query | High WAL = write-heavy. If one query generates most WAL, it's driving replication lag and checkpoint pressure |
| `local_blks_hit` / `local_blks_read` | Blocks for temporary tables | If nonzero, query uses temp tables — common in complex CTEs or materialized subqueries |

#### Red Flags — What Demands Explanation

| Signal | What It Means | Example | What to Tell the Customer |
|--------|---------------|---------|---------------------------|
| Low cache_hit_pct (< 90%) | Query hitting disk constantly | `cache_hit_pct: 47.19` | "This query reads X blocks from disk each call. The table it touches (Y) is Z GB but shared_buffers is only W MB — the data physically cannot stay cached" |
| High temp_blks (any nonzero) | Query spilling sorts/hashes to disk | `temp_blks_written: 39102928` | "This query spills ~X GB to temp files per execution because work_mem (Y MB) is too small for its sort/hash. Each spill means disk I/O instead of memory" |
| Huge rows_per_call (>1000) | Missing pagination or bulk fetch | `rows_per_call: 12177` | "Each call returns ~12K rows. If this is a user-facing query, it likely needs LIMIT/OFFSET or cursor-based pagination. If it's a batch job, it's expected" |
| Near-zero rows_per_call with high calls | Polling or existence check pattern | 0.01 rows/call, 500K calls | "This query runs 500K times but almost never finds data. If it's checking for new work, consider LISTEN/NOTIFY instead of polling. If it's an existence check, ensure it uses EXISTS with LIMIT 1" |
| stddev >> mean | Wildly variable performance | mean=15ms, stddev=2400ms, max=45000ms | "This query averages 15ms but sometimes takes 45 SECONDS. The high stddev means unpredictable latency. Likely causes: lock contention, cache misses on cold data, or table bloat causing variable scan times" |
| High mean_plan_ms (>5ms) | Expensive query planning | `mean_plan_ms: 23.4` | "The planner spends 23ms just deciding HOW to run this query, before executing it. With X calls, that's Y minutes of pure planning overhead. Consider: PREPARE'd statements, simpler joins, or increasing default_statistics_target for better stats" |
| shared_blks_written > 0 | Memory pressure forcing query I/O | `shared_blks_written: 50000` | "This query was forced to flush dirty pages to disk itself because shared_buffers was full. This is a sign of severe buffer pool pressure — increase shared_buffers" |
| High wal_bytes relative to others | Write-heavy query driving replication | `wal_bytes: 5000000000` | "This query generates X GB of WAL, which is Y% of total WAL. It's the primary driver of replication lag and checkpoint I/O" |
| max_ms >> 10× mean_ms | Pathological worst cases | mean=50ms, max=120000ms | "The worst execution was 2400× slower than average. Investigate: was it blocked by a lock? Did it hit a cold cache after restart? Is there table bloat causing some scans to be much longer?" |

#### How to Present Slow Queries

**Show the full table first** with all available metrics (the report already includes these columns):

```
| Query (truncated) | Calls | Total (min) | Mean (ms) | Min/Max (ms) | Stddev | Rows/Call | Cache Hit | Temp R/W | Plan (ms) | I/O Time |
|-------------------|-------|-------------|-----------|--------------|--------|-----------|-----------|----------|-----------|----------|
| SELECT Email.ccFull... | 78K | 132 | 101 | 0.3/8200 | 340 | 0.05 | 47% | 0/0 | 1.2 | 45000 |
| SELECT Thread... ORDER BY | 48K | 223 | 279 | 2.1/45000 | 2400 | 12,177 | 98.8% | 0/39M | 0.4 | 800 |
| SELECT Content... | 1.3K | 12 | 563 | 180/3200 | 420 | 0.65 | 1.8% | 0/0 | 8.3 | 31000 |
```

**Then analyze EACH query** — this is the most valuable part. For each of the top 10 queries, explain:

1. **What the query does** — identify the tables, the pattern (lookup, join, aggregation, pagination)
2. **Why it's slow** — connect the specific metrics to a root cause
3. **The cascading impact** — how this query affects overall database health
4. **Specific fix** — not generic advice, but targeted to what the metrics show

Example deep analysis:

> **Query 1: Email.ccFull join** (78K calls, 101ms mean, 132 min total)
> - **Pattern**: Joins Email → EmailThreadKind → Thread → EmailEntry. ORM-generated N+1 or bulk join.
> - **Root cause**: 47% cache hit means 53% of blocks come from disk. The Email table is 1.7GB but shared_buffers is 128MB — only 7.5% of this table can be cached at once. Every call displaces other data from cache, creating a cascading eviction problem.
> - **The stddev of 340ms** with max of 8200ms means some calls take 80× longer — likely when the needed pages were just evicted by another query.
> - **I/O time of 45,000ms** total confirms this: the query has spent 45 seconds just waiting for disk across all calls.
> - **rows_per_call = 0.05** means it almost never finds a match — it's doing all this I/O for an existence-check pattern. An `EXISTS()` subquery with proper index could eliminate the full table scan.
> - **Fix**: (a) Increase shared_buffers to 1GB so the hot portion stays cached. (b) Add index on Email(ccFull, threadId) to avoid the sequential scan. (c) Rewrite as EXISTS if the app only needs presence, not the full row.

> **Query 2: Thread pagination** (48K calls, 279ms mean, 223 min total)
> - **Pattern**: SELECT Thread... ORDER BY with large result set. Pagination query.
> - **Root cause**: rows_per_call = 12,177 — returning 12K rows per call is a pagination bug (missing LIMIT) or an admin/batch endpoint.
> - **temp_blks_written = 39M** (312 GB of temp files!) — the ORDER BY creates a sort that exceeds work_mem (4MB), so it spills to disk every single time.
> - **stddev = 2400ms with max = 45,000ms** — some executions take 45 seconds, likely when disk temp files compete with other I/O.
> - **Cache hit is 98.8%** — the data itself is cached, but the sort still spills because work_mem is separate from shared_buffers.
> - **Fix**: (a) Add `LIMIT` if this is user-facing. (b) Create an index matching the ORDER BY clause to eliminate the sort entirely. (c) Increase work_mem to 32-64MB so the sort fits in memory.

#### Truncate Long Queries Intelligently
- Show the table names and key operations (JOIN, WHERE, ORDER BY)
- Don't dump 2000-character ORM-generated SQL
- Identify the pattern: "Thread zone assignment lookup" not the full SQL
- For ORM queries with `$1, $2, ...` parameters, note that the actual values aren't available — the pattern matters more than specific values
- **Note on query truncation**: pg_stat_statements stores full query text up to `track_activity_query_size` (default 1024 chars). ORM-generated queries often exceed this — if a query ends abruptly, it was truncated by PostgreSQL, not by our script. The JSON output preserves the full text from pg_stat_statements; only the human-readable text report truncates for display

#### Query Workload Profile

After analyzing individual queries, summarize the overall workload:
- **Read vs write ratio**: Use tup_returned/tup_fetched vs tup_inserted/tup_updated/tup_deleted from database_stats
- **Top 3 time consumers**: Which queries dominate total_min? If 3 queries account for 80% of execution time, that's where to focus
- **Cache pressure sources**: Which queries have the most shared_blks_read? They're driving cache misses for everything else
- **Temp file culprits**: Which specific queries create temp files? Don't say "increase work_mem" generically — say "Query X creates Y GB of temp files per day"
- **WAL generators**: If applicable, which queries generate the most WAL bytes? They're driving replication lag

### Correlate Across Sections

The script collects many data points. Look for correlations:

| If you see... | Check also... | Because... |
|---------------|---------------|------------|
| Low table cache hit | per-table cache rates, table sizes vs shared_buffers | One large table may be thrashing the cache |
| High temp files | work_mem value, top queries | Specific queries may be the culprits |
| Dead rows building up | vacuum health, XID age | Autovacuum may be blocked or misconfigured |
| Seq scans on large tables | unused indexes, index hit rates | May have indexes but planner isn't using them |
| High connection usage | connection age, idle_in_transaction | May be leaks, not actual load |

### Synthesize Insights the Script Can't

The script flags individual issues. You should:

1. **Identify the PRIMARY bottleneck** - What's the #1 thing hurting performance right now?
2. **Explain cascading effects** - How does one problem cause others?
3. **Prioritize fixes** - What should they do first, second, third?
4. **Warn about risks** - What happens if they don't fix this?

**Important:** Synthesis is prose that EXPLAINS the data tables you already showed. Don't hide data in prose - the tables make it visible, the prose connects the dots.

Example flow:
1. Show config table: `shared_buffers = 128 MB` vs recommended `1 GB`
2. Show cache table: `Email` table at 6% cache hit with 1.19B disk reads
3. THEN explain: "Your buffer pool (128 MB) is 13x smaller than your Email table (1.7 GB). This single table is dragging down your overall 89% cache hit rate."

The user sees the data, understands the relationship, then gets the explanation. Don't make them trust your conclusions without seeing the evidence first.

## Running the Analysis

Pass project, environment, and service IDs directly — no `railway link` needed:

```bash
# From plugins/railway/skills/use-railway directory:
python3 scripts/analyze-<type>.py \
  --service <name> \
  --type <type> \
  --json \
  --project-id <project-id> \
  --environment-id <env-id> \
  --service-id <service-id>
```

All three IDs come from the URL (see "Context: URL First" above). The service name comes from the API query.

**Options:**
- `--metrics-hours <N>` — Hours of metrics history to fetch (default: 24, max: 168). Use `--metrics-hours 168` for 7-day trends, `--metrics-hours 1` for recent snapshot.

**SSH retry:** The script automatically retries SSH connectivity up to 3 times with increasing timeouts (30s, 60s, 90s). If the database query itself fails after SSH connects, it retries once. Progress is logged to stderr.

**Output:** Progress messages go to stderr. JSON results go to stdout. Do not redirect or pipe stderr — just run the command as-is and read the full output.

### Resolving environment by name

If the URL has no `environmentId` and the user specifies an environment by name (e.g., "production"), resolve it:

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

### Debugging individual steps

```bash
python3 scripts/analyze-<type>.py --service <name> --type <type> \
  --project-id <pid> --environment-id <eid> --service-id <sid> \
  --step ssh-test    # Test SSH connectivity
  --step query       # Run only the database query
  --step metrics     # Fetch only API metrics
  --step logs        # Fetch only logs
```

## Database-Specific References

After running the script and checking collection status, load the reference for the specific database type:

| Database | Reference | What It Covers |
|----------|-----------|----------------|
| PostgreSQL | [analyze-db-postgres.md](analyze-db-postgres.md) | What psql collects, log analysis checklist, tuning formulas, vacuum priority, pg_stat_statements, applying fixes |
| MySQL | [analyze-db-mysql.md](analyze-db-mysql.md) | All 12 metric sections (overview, query throughput, InnoDB, efficiency, buffer pool, I/O, network, locks, cache, top queries, tables, active queries), patterns, tuning |
| Redis | [analyze-db-redis.md](analyze-db-redis.md) | INFO ALL metrics, memory fragmentation, cache thrashing, persistence, command stats |
| MongoDB | [analyze-db-mongo.md](analyze-db-mongo.md) | serverStatus, WiredTiger cache, query efficiency, connection saturation, oplog |

**Always load the DB-specific reference** — it contains the metric sections, thresholds, and tuning knowledge needed for proper analysis.

## Infrastructure Metrics (All Database Types)

All scripts collect the same infrastructure metrics via Railway API:

**Metrics History (`metrics_history`):**
The script fetches **7 days** (168 hours) of time-series data from Railway's metrics API by default and produces **two analysis windows**:

```json
{
  "metrics_history": {
    "windows": {
      "7d": { "window_hours": 168, "metrics": { "cpu": {...}, "memory": {...}, ... } },
      "24h": { "window_hours": 24, "metrics": { "cpu": {...}, "memory": {...}, ... } }
    }
  }
}
```

Each window independently computes:
- **Summary stats**: current, min, max, avg for each metric
- **Trend analysis**: compares first-quarter avg to last-quarter avg — reports direction (increasing/decreasing/stable) and % change
- **Spike detection**: flags values > avg + 2*stddev with timestamps of peaks
- **Downsampled series**: ~48 data points per window

Available metrics: CPU, memory (with limits), disk, network RX/TX.

**Comparing windows reveals whether a trend is new or sustained:**
- "Memory increasing in 24h but stable over 7d" → temporary spike, likely a batch job
- "Memory increasing in both 24h AND 7d" → sustained growth, may need investigation
- "CPU spike in 24h, no spikes in 7d" → new issue
- "Disk growing over 7d" → data accumulation trend

Use `--metrics-hours N` to change the long window (default: 168, max: 168). The 24h window is always produced when the long window is > 24h.

### Railway auto-scales vertically

Railway services auto-scale CPU, RAM, and disk based on actual usage. Users do NOT pick or control resource sizes. The `cpu_limit` and `memory_limit` values from metrics are the **autoscale ceiling** (typically 32 vCPU / 32 GB), not user-provisioned allocations. Users are billed for actual usage, not the ceiling.

**Rules for ALL database types:**
- **Never say "right-size the instance"** or suggest reducing CPU/RAM — it's not a user action.
- **Never flag low utilization % against the limit as waste** — a service showing 0.01 vCPU / 70 MB actual usage against a 32 vCPU / 32 GB ceiling is normal, not over-provisioned.
- **Disk is also auto-provisioned** — volume size grows as needed. Users pay for actual disk used, not some pre-allocated amount.
- **Focus on actual usage values**, not the ratio to limits. Analyze whether 70 MB of memory is healthy for this workload — don't compare it to the 32 GB ceiling.
- When tuning database parameters (shared_buffers, innodb_buffer_pool_size, maxmemory, etc.), base recommendations on the **current actual RAM** from `metrics_history.memory`, not the limit.
