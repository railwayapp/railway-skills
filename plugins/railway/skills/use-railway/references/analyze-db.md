# Database Analysis

## Your Role

You are a database performance expert. The script collects raw data - your job is to **think deeply** about what you see, identify root causes, correlate symptoms, and explain the "why" behind problems.

**Don't just report metrics. Analyze them.**

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

### Slow Query Analysis

The `top_queries` array contains valuable performance data. Don't just list the slowest queries - analyze them:

**Red flags to look for:**

| Signal | What It Means | Example |
|--------|---------------|---------|
| Low cache_hit_pct (< 90%) | Query hitting disk constantly | `cache_hit_pct: 47.19` |
| High temp_blks_read/written | Query spilling to disk | `temp_blks_written: 39102928` |
| Huge rows returned | Pagination bug or missing LIMIT | `rows: 583120179` from 47K calls |
| High mean_ms (> 500ms) | Slow query pattern | `mean_ms: 1078.0` |
| Low rows vs high calls | Scanning lots to return little | 843 rows from 1289 calls with 31M disk reads |

**How to present slow queries:**

Show a table with the key metrics, then analyze:

```
| Query (truncated) | Calls | Mean | Cache Hit | Temp Blocks | Rows/Call |
|-------------------|-------|------|-----------|-------------|-----------|
| SELECT Email.ccFull... | 78K | 101ms | 47% | 0 | 0.05 |
| SELECT Thread... ORDER BY | 48K | 279ms | 98.8% | 39M | 12,177 |
| SELECT Content... | 1.3K | 563ms | 1.8% | 0 | 0.65 |
```

Then explain:
- **Email.ccFull query**: 47% cache hit with 1.1B disk reads is the worst offender. Joining across Email → EmailThreadKind → Thread → EmailEntry without proper indexing.
- **Thread pagination query**: Returning 12K rows per call with 39M temp blocks suggests ORDER BY without proper index, spilling to disk for sorts.
- **Content query**: 1.8% cache hit for 31M disk reads to return 843 rows - scanning entire Content table repeatedly.

**Truncate long queries intelligently:**
- Show the table names and key operations (JOIN, WHERE, ORDER BY)
- Don't dump 2000-character ORM-generated SQL
- Identify the pattern: "Thread zone assignment lookup" not the full SQL

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

```bash
# From plugins/railway/skills/use-railway directory:
python3 scripts/analyze-db.py --service <name> --type postgres --json
```

Before running, link to the correct project/environment/service:
```bash
railway link --project <project-id> --environment <env-id> --service <service-id>
```

## What the Script Collects

All in ONE operation (no additional queries needed):

**Connections:**
- Current/max/available counts
- States (active, idle, idle_in_transaction)
- By application name
- By age (buckets: <1min, 1-5min, 5-30min, 30min-1hr, 1-24hr, >24hr)
- Oldest connection age

**Memory & Configuration:**
- shared_buffers, effective_cache_size, work_mem, maintenance_work_mem
- WAL settings, parallelism settings, planner settings
- Autovacuum status

**Cache Performance:**
- Overall table/index hit ratios
- Per-table: hit %, disk reads, size (this is key for diagnosis)

**Storage:**
- Database size, WAL size
- Per-table: total size, data size, index size, row count

**Vacuum Health:**
- Per-table: dead rows, dead %, vacuum count, last vacuum/analyze, XID age
- Flags: needs_vacuum, needs_freeze

**Indexes:**
- Unused indexes (0 scans) with sizes
- Invalid indexes (failed builds)

**Query Performance (if pg_stat_statements enabled):**
- Top queries by execution time
- Per-query: calls, total time, mean time, cache hit %, temp blocks
- Temp file stats (cumulative since stats reset, NOT current disk usage)

**Logs & Active Issues:**
- `recent_logs`: Raw unfiltered logs (1000 lines) - parse these yourself, look for errors, warnings, patterns
- `recent_errors`: Filtered error-level logs (legacy, for quick reference)
- `long_running_queries`: Queries running >5s at time of collection
- `blocked_queries`: Queries waiting on locks
- `cluster_logs`: HA cluster events (Patroni)

**Important:** Always analyze the raw `recent_logs` array. Look for:
- Error patterns (connection failures, OOM, disk space)
- Warning patterns (autovacuum issues, checkpoint warnings)
- Startup/restart events
- Replication issues
- Slow query warnings

State what you found: "X errors, Y warnings, patterns observed: ..." or "1000 log lines examined, no concerning patterns".

**Active Issues:**
- Long-running queries (>5s)
- Idle in transaction (>30s)
- Blocked queries (waiting on locks)
- Lock contention details

**Infrastructure:**
- Disk usage %
- CPU/memory usage
- Replication status
- HA cluster status (Patroni)
- Background writer stats
- WAL archiver status

## PostgreSQL Tuning Knowledge

Use this to reason about configuration issues:

### Memory Parameters

| Parameter | Default | Target | What It Does |
|-----------|---------|--------|--------------|
| `shared_buffers` | 128MB | 25% RAM | The database's main cache. Pages read from disk go here. Too small = constant disk I/O. |
| `effective_cache_size` | 4GB | 75% RAM | NOT memory allocation - a hint to the planner about OS cache. Too low = planner avoids indexes. |
| `work_mem` | 4MB | 16-64MB | Memory per sort/hash/join operation. Too low = temp files on disk. Caution: multiplied by concurrent operations. |
| `maintenance_work_mem` | 64MB | 256MB-1GB | Memory for VACUUM, CREATE INDEX. Higher = faster maintenance. |

### Tuning Formulas

```
shared_buffers = RAM × 0.25 (max 40%)
  1GB RAM  → 256MB
  4GB RAM  → 1GB
  16GB RAM → 4GB

work_mem = (RAM / max_connections) / 4
  4GB RAM, 100 conns → 10MB
  8GB RAM, 200 conns → 10MB

effective_cache_size = RAM × 0.75
  4GB RAM  → 3GB
  16GB RAM → 12GB
```

### Settings Requiring Restart vs Immediate

**Restart required:**
- shared_buffers
- max_connections
- max_parallel_workers

**Immediate (SIGHUP):**
- work_mem
- effective_cache_size
- random_page_cost
- checkpoint_completion_target

### SSD vs HDD

Railway uses SSDs. If `random_page_cost = 4.0` (HDD default), the planner thinks random reads are 4x more expensive than sequential - it avoids index scans. Set to 1.1-2.0 for SSDs.

## Thresholds for Reasoning

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Cache hit ratio | >99% | 95-99% | <95% |
| Per-table cache hit | >95% | 80-95% | <80% with high reads |
| Connection usage | <70% | 70-90% | >90% |
| Disk usage | <70% | 70-85% | >85% |
| Dead rows % | <5% | 5-20% | >20% |
| XID age | <100M | 100-150M | >150M (emergency at 2B) |

### Vacuum Priority Matrix

Dead row percentage alone doesn't determine urgency. Use this matrix:

| Table Size | Dead Rows | Priority |
|------------|-----------|----------|
| > 100 MB | > 10,000 | High - real bloat affecting performance |
| > 50 MB | > 5,000 | Medium - worth addressing |
| < 10 MB | Any | Low - negligible impact, ignore |
| Any | < 1,000 | Low - autovacuum will handle it |

A 1 MB table with 25% dead rows has ~250 KB of bloat. Not worth mentioning as "critical".

## Applying Fixes

When recommending changes, include the actual SQL:

```sql
-- Memory tuning (example for 4GB RAM)
ALTER SYSTEM SET shared_buffers = '1GB';
ALTER SYSTEM SET effective_cache_size = '3GB';
ALTER SYSTEM SET work_mem = '32MB';
ALTER SYSTEM SET random_page_cost = 1.5;
SELECT pg_reload_conf();
-- Note: shared_buffers requires restart
```

```sql
-- Vacuum specific tables
VACUUM ANALYZE "TableName";

-- Emergency XID freeze
VACUUM FREEZE "TableName";
```

## Enabling pg_stat_statements

**ONLY suggest this if BOTH conditions are true:**
1. `pg_stat_statements_installed` is `false` in the JSON output
2. `top_queries` is empty or missing

If these conditions are met, tell the user to run (do NOT execute with Bash):

```
python3 scripts/enable-pg-stats.py --service <name>
```

This may require a brief restart.

**If `pg_stat_statements_installed: true` and `top_queries` has data, DO NOT suggest enabling it.**

## Validated against

- PostgreSQL system views: pg_stat_activity, pg_stat_statements, pg_statio_user_tables, pg_stat_user_tables
- Patroni REST API for HA clusters
