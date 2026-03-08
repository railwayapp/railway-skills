# Database Analysis

## Analysis Protocol

The script collects ALL the data you need in one pass, including:
- Per-table cache hit rates (not just overall)
- Table sizes vs shared_buffers
- Dead rows per table with vacuum timestamps
- Index usage per table
- Slow queries with execution details
- **Recommendations with root causes already identified**

**Your job is to EXPLAIN the findings, not just report them.**

### How to Present Results

For every anomaly the script identifies:

1. **State the problem** - What's wrong
2. **Explain the cause** - Use the detailed data from the script to show WHY (e.g., compare table size to shared_buffers)
3. **Give the fix** - Use the recommendations from the script

### Example: Low Cache Hit

The script output includes:
- `cache_hit.table_hit_pct: 90`
- `cache_per_table: [{table: "Email", hit_pct: 6.3, disk_reads: 1190000000, size: "1.7 GB"}]`
- `memory_config.shared_buffers.mb: 128`
- `recommendations: [{issue: "Table 'Email' has 6% cache hit...", action: "Increase shared_buffers..."}]`

❌ Bad: "Cache hit ratio is 90%"

✅ Good: "Cache hit is 90% because the Email table (1.7GB) has only 6% cache hit with 1.19B disk reads. Your shared_buffers is 128MB - the Email table alone is 13x larger than the entire buffer pool. Every query touching Email hits disk.

**Fix**: Increase shared_buffers to 1GB (25% of RAM)..."

### Key Principle

The script already collected the evidence. Your job is to connect the dots and make the explanation clear. Don't just echo the recommendations - explain the reasoning using the data.

## Use the Script

```bash
# From plugins/railway/skills/use-railway directory:
python3 scripts/analyze-db.py --service <name> --type postgres --json
```

That's it. Run the script, use its output.

## Before running

Link to the correct project/environment/service:

```bash
railway link --project <project-id> --environment <env-id> --service <service-id>
```

## What the script collects

All of this in ONE operation:

- Connection stats (current, max, active, idle, by app, by age)
- Full PostgreSQL configuration for tuning analysis:
  - Memory: shared_buffers, effective_cache_size, work_mem, maintenance_work_mem
  - WAL: wal_buffers, checkpoint_completion_target, min/max_wal_size
  - Parallelism: max_parallel_workers, max_parallel_workers_per_gather
  - Planner: random_page_cost, default_statistics_target
  - Durability: synchronous_commit, autovacuum settings
- Cache hit ratios (overall and per-table)
- Database stats (deadlocks, temp files)
- Size breakdown (database, WAL, tables, indexes, system)
- Table sizes with row counts
- Vacuum health (dead rows, XID age, needs_vacuum/needs_freeze)
- Unused indexes
- Sequential scan patterns (missing index candidates)
- Top queries by execution time (if pg_stat_statements available)
- Long-running queries
- Idle in transaction
- Blocked queries and lock contention
- Replication status
- HA cluster status (Patroni)
- Recent error logs
- Prioritized recommendations

## Output formats

**Text report** (default): Human-readable with markdown tables
```bash
python3 scripts/analyze-db.py --service <name> --type postgres
```

**JSON** (for analysis): Raw data structures
```bash
python3 scripts/analyze-db.py --service <name> --type postgres --json
```

## Handling errors

The script handles missing extensions gracefully. If `pg_stat_statements` is not installed, `top_queries` will be empty - that's expected.

For any other errors, the script reports them in the `errors` field and continues collecting other metrics. Use the partial data.

## Enabling pg_stat_statements

**USER-ONLY COMMAND: Do NOT execute this with Bash. Show the command and ask the user to run it.**

If the analysis shows "pg_stat_statements extension not available", tell the user:

```
To enable query performance tracking, run this command in your terminal:

python3 scripts/enable-pg-stats.py --service <name>

This may require a database restart (brief downtime).
```

This script replicates the frontend's Stats tab enable logic:
1. Checks if `pg_stat_statements` is already in `shared_preload_libraries`
2. If already loaded, just installs the extension (no restart needed)
3. If not loaded:
   - Installs the extension: `CREATE EXTENSION IF NOT EXISTS pg_stat_statements`
   - Configures `shared_preload_libraries` via `ALTER SYSTEM`
   - Restarts the database service (brief downtime)

After the user runs the command, verify with a read-only query:
```sql
SHOW shared_preload_libraries;
SELECT * FROM pg_stat_statements LIMIT 5;
```

## Managing PostgreSQL extensions

**USER-ONLY COMMANDS: Do NOT execute install/uninstall with Bash. Show the command and ask the user to run it.**

**Safe commands (can execute with Bash):**
```bash
# List all available and installed extensions
python3 scripts/pg-extensions.py --service <name> list

# Get extension info
python3 scripts/pg-extensions.py --service <name> info pg_stat_statements --json
```

**User-only commands (show to user, do NOT execute):**
```
# Install an extension - USER MUST RUN THIS
python3 scripts/pg-extensions.py --service <name> install postgis

# Uninstall an extension - USER MUST RUN THIS
python3 scripts/pg-extensions.py --service <name> uninstall postgis
```

The script handles:
- Dependency resolution: shows required dependencies before install
- Dependent checking: prevents uninstall if other extensions depend on it
- CASCADE install: automatically installs required dependencies
- Version pinning: `--version` flag for specific versions

Common extensions:
- `pg_stat_statements` - Query performance tracking
- `postgis` - Geographic objects
- `pg_trgm` - Trigram text search
- `uuid-ossp` - UUID generation
- `hstore` - Key-value storage

## PostgreSQL Configuration Tuning

The analysis script collects key PostgreSQL configuration parameters and provides tuning recommendations. Here's what each parameter does and how to tune it.

### Memory Parameters (Most Critical)

| Parameter | Default | Recommended | Purpose |
|-----------|---------|-------------|---------|
| `shared_buffers` | 128MB | 25% of RAM (max 40%) | Data page caching - most impactful setting |
| `effective_cache_size` | 4GB | 50-75% of RAM | Helps query planner estimate available cache |
| `work_mem` | 4MB | 16-64MB | Memory per sort/hash operation |
| `maintenance_work_mem` | 64MB | 256MB-1GB | Memory for VACUUM, CREATE INDEX |

### WAL & Checkpoint Parameters

| Parameter | Default | Recommended | Purpose |
|-----------|---------|-------------|---------|
| `wal_buffers` | -1 (auto) | 16MB | WAL write buffer |
| `checkpoint_completion_target` | 0.9 | 0.9 | Spread checkpoint I/O |
| `min_wal_size` | 80MB | 1GB | Minimum WAL size |
| `max_wal_size` | 1GB | 4GB+ | Maximum WAL before checkpoint |

### Parallelism

| Parameter | Default | Recommended | Purpose |
|-----------|---------|-------------|---------|
| `max_parallel_workers` | 8 | CPU cores | Total parallel workers |
| `max_parallel_workers_per_gather` | 2 | 2-4 | Workers per query operation |

### Query Planner

| Parameter | Default | Recommended | Purpose |
|-----------|---------|-------------|---------|
| `random_page_cost` | 4.0 | 1.1-2.0 (SSD) | Cost estimate for random I/O |
| `default_statistics_target` | 100 | 100-500 | Statistics sampling depth |

### Durability vs Performance

| Parameter | Default | Recommended | Trade-off |
|-----------|---------|-------------|-----------|
| `synchronous_commit` | on | on (safe) | off = faster but may lose recent transactions on crash |
| `autovacuum` | on | on | NEVER disable - causes bloat and XID wraparound |

### Tuning Formulas

**shared_buffers**: `RAM * 0.25` (max 40% of RAM)
```
1GB RAM  -> 256MB
4GB RAM  -> 1GB
16GB RAM -> 4GB
```

**work_mem**: `(RAM / max_connections) / 4`
```
4GB RAM, 100 connections -> (4096 / 100) / 4 = 10MB
8GB RAM, 200 connections -> (8192 / 200) / 4 = 10MB
```

**effective_cache_size**: `RAM * 0.75`
```
4GB RAM  -> 3GB
16GB RAM -> 12GB
```

### Warning Signs

The script flags these conditions:
- `shared_buffers < 128MB` - likely at default, increase to 25% RAM
- `work_mem = 4MB` with high temp file usage - queries spilling to disk
- `random_page_cost = 4.0` - HDD default, set to 1.1-2.0 for Railway SSDs
- `autovacuum = off` - CRITICAL, will cause database failure
- `checkpoint_completion_target < 0.9` - may cause I/O spikes

### How to Change Settings

**Via SQL (some settings):**
```sql
ALTER SYSTEM SET shared_buffers = '1GB';
SELECT pg_reload_conf();  -- For dynamic settings
-- Restart required for shared_buffers
```

**Settings requiring restart:**
- shared_buffers
- max_connections
- max_parallel_workers

**Settings that take effect immediately (SIGHUP):**
- work_mem
- effective_cache_size
- random_page_cost
- checkpoint_completion_target

## Thresholds

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Cache hit ratio | >99% | 95-99% | <95% |
| Connection usage | <70% | 70-90% | >90% |
| Disk usage | <70% | 70-85% | >85% |
| Dead rows % | <5% | 5-20% | >20% |
| XID age | <100M | 100-150M | >150M |
| Replication lag | <1s | 1-10s | >10s |
| shared_buffers | >256MB | 128-256MB | <128MB |
| work_mem (with temp files) | adequate | 4MB default | 4MB + high temp |

## Common recommendations

### Low cache hit ratio
- Check if shared_buffers is undersized relative to working set
- Identify tables with worst hit rates (script shows these)
- Look for sequential scans on large tables
- **Tuning**: Increase `shared_buffers` to 25% of RAM

### High temp file usage (queries spilling to disk)
- Sorts, hashes, and joins are using disk instead of memory
- **Tuning**: Increase `work_mem` from default 4MB to 16-64MB
- Caution: Each sort/hash operation uses this much memory

### Default configuration detected
If the script shows many "Default" or "Low" status values:
```sql
-- Check current settings
SHOW shared_buffers;
SHOW work_mem;
SHOW effective_cache_size;
SHOW random_page_cost;

-- Apply optimizations (example for 4GB RAM)
ALTER SYSTEM SET shared_buffers = '1GB';
ALTER SYSTEM SET effective_cache_size = '3GB';
ALTER SYSTEM SET work_mem = '32MB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
ALTER SYSTEM SET random_page_cost = 1.5;
ALTER SYSTEM SET checkpoint_completion_target = 0.9;

-- Reload configuration
SELECT pg_reload_conf();
-- Note: shared_buffers requires restart
```

### Vacuum needed
```sql
VACUUM ANALYZE "TableName";
```

### High connection usage
- Use connection pooling (PgBouncer)
- Check for connection leaks

### Unused indexes
```sql
DROP INDEX IF EXISTS "index_name";
```

### Poor query plans (SSD optimization)
If `random_page_cost` is at HDD default (4.0):
```sql
ALTER SYSTEM SET random_page_cost = 1.5;
SELECT pg_reload_conf();
```

## Validated against

- Postgres system views: pg_stat_activity, pg_stat_statements, pg_statio_user_tables
- Patroni REST API for HA clusters
