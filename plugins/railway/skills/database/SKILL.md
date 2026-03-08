---
name: database
description: This skill should be used when the user wants to add a database (Postgres, Redis, MySQL, MongoDB), analyze a database, introspect database health, check connections, query database metrics, says "add postgres", "add redis", "add database", "analyze db", "check database", "database health", or "wire up the database". For other templates (Ghost, Strapi, n8n, etc.), use the templates skill.
allowed-tools: Bash(railway:*), Bash(curl:*)
---

# Database

Add and analyze Railway database services.

## Intent routing

| Intent | Action |
|--------|--------|
| Add/create database | [Adding a Database](#adding-a-database) |
| Analyze/introspect | [Complete Database Analysis](#complete-database-analysis) |
| Connect service | [Connecting to the Database](#connecting-to-the-database) |

## Adding a Database

| Database | Template Code |
|----------|---------------|
| PostgreSQL | `postgres` |
| Redis | `redis` |
| MySQL | `mysql` |
| MongoDB | `mongodb` |

## Connecting to the Database

| Database | Variable Reference |
|----------|-------------------|
| PostgreSQL | `${{Postgres.DATABASE_URL}}` |
| Redis | `${{Redis.REDIS_URL}}` |
| MySQL | `${{MySQL.MYSQL_URL}}` |
| MongoDB | `${{MongoDB.MONGO_URL}}` |

## Complete Database Analysis

**IMPORTANT**: Always run ALL checks. When ANY metric shows WARNING or CRITICAL, run the corresponding deep investigation before making recommendations. Never suggest fixes without understanding root cause.

### Step 1: Resolve Service Instance ID

```bash
# Get workspaces
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query { me { workspaces { id } } }' '{}'

# Search for service instance
${CLAUDE_PLUGIN_ROOT}/skills/lib/railway-api.sh \
  'query { workspace(workspaceId: "WORKSPACE_ID") {
    projects { edges { node {
      id name
      environments { edges { node {
        id name
        serviceInstances { edges { node {
          id serviceName serviceId
        } } }
      } } }
    } } }
  } }' '{}'
```

### Step 2: Container Resources

```bash
railway ssh --project <p> --service <s> --environment <e> -- 'free -h'
railway ssh --project <p> --service <s> --environment <e> -- 'df -h'
railway ssh --project <p> --service <s> --environment <e> -- 'uptime'
railway ssh --project <p> --service <s> --environment <e> -- 'ps aux --sort=-%mem | head -10'
```

### Step 3: All Core Metrics

Run ALL of these for every Postgres analysis:

```bash
# Connection states
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT state, count(*) FROM pg_stat_activity GROUP BY state;"'

# Connection pool
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as current_conns, (SELECT setting::int FROM pg_settings WHERE name = '\''max_connections'\'') as max_conns;"'

# Cache hit ratios
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT ROUND(100.0 * sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) as table_cache_pct, ROUND(100.0 * sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0), 2) as index_cache_pct FROM pg_statio_user_tables;"'

# Database sizes
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY pg_database_size(datname) DESC;"'

# Table sizes
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT relname as table_name, pg_size_pretty(pg_total_relation_size(relid)) as total_size FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 15;"'

# Dead rows / vacuum health
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT relname, n_dead_tup, n_live_tup, CASE WHEN n_live_tup > 0 THEN ROUND(100.0 * n_dead_tup / n_live_tup, 2) ELSE 0 END as dead_pct, last_autovacuum, last_autoanalyze FROM pg_stat_user_tables WHERE n_dead_tup > 100 ORDER BY n_dead_tup DESC LIMIT 15;"'

# XID age
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT datname, age(datfrozenxid) as xid_age FROM pg_database ORDER BY age(datfrozenxid) DESC;"'

# Unused indexes
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT relname, indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) as size, idx_scan FROM pg_stat_user_indexes WHERE idx_scan = 0 ORDER BY pg_relation_size(indexrelid) DESC LIMIT 15;"'

# Long queries
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT pid, now() - query_start AS duration, state, LEFT(query, 80) FROM pg_stat_activity WHERE state != '\''idle'\'' AND query_start < now() - interval '\''5 seconds'\'' ORDER BY query_start LIMIT 10;"'

# Lock contention
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT l.locktype, l.mode, a.usename, a.state, LEFT(a.query, 60) FROM pg_locks l JOIN pg_stat_activity a ON l.pid = a.pid WHERE a.datname = current_database() AND NOT l.granted LIMIT 10;"'

# Replication (if applicable)
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT client_addr, state, sent_lsn, replay_lsn, (pg_wal_lsn_diff(sent_lsn, replay_lsn)/1024/1024)::int as lag_mb FROM pg_stat_replication;"'
```

### Step 4: Deep Investigation (REQUIRED when warnings found)

#### IF cache hit ratio < 95%

```bash
# Check shared_buffers setting
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT name, setting, unit, context FROM pg_settings WHERE name IN ('\''shared_buffers'\'', '\''effective_cache_size'\'', '\''work_mem'\'', '\''maintenance_work_mem'\'');"'

# Check buffer usage by table
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT c.relname, pg_size_pretty(pg_relation_size(c.oid)) as size, heap_blks_read, heap_blks_hit, ROUND(100.0 * heap_blks_hit / nullif(heap_blks_hit + heap_blks_read, 0), 2) as hit_pct FROM pg_statio_user_tables s JOIN pg_class c ON s.relid = c.oid WHERE heap_blks_read > 0 ORDER BY heap_blks_read DESC LIMIT 10;"'

# Check if working set exceeds shared_buffers
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT pg_size_pretty(sum(pg_relation_size(relid))) as total_table_size FROM pg_stat_user_tables;"'

# Check for sequential scans on large tables (missing indexes)
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT relname, seq_scan, seq_tup_read, idx_scan, pg_size_pretty(pg_relation_size(relid)) as size FROM pg_stat_user_tables WHERE seq_scan > 0 AND pg_relation_size(relid) > 10000000 ORDER BY seq_tup_read DESC LIMIT 10;"'
```

#### IF dead rows > 10% on any table

```bash
# Check autovacuum settings
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT name, setting FROM pg_settings WHERE name LIKE '\''autovacuum%'\'' OR name LIKE '\''vacuum%'\'';"'

# Check if autovacuum is running
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT pid, datname, relid::regclass, phase, heap_blks_total, heap_blks_scanned, heap_blks_vacuumed FROM pg_stat_progress_vacuum;"'

# Check for long-running transactions blocking vacuum
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT pid, usename, state, xact_start, now() - xact_start as duration, LEFT(query, 60) FROM pg_stat_activity WHERE xact_start IS NOT NULL AND state != '\''idle'\'' ORDER BY xact_start LIMIT 10;"'

# Check table-specific autovacuum settings
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT relname, reloptions FROM pg_class WHERE reloptions IS NOT NULL AND relkind = '\''r'\'';"'

# Check dead tuple threshold for problematic tables
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT relname, n_live_tup, n_dead_tup, (SELECT setting::int FROM pg_settings WHERE name = '\''autovacuum_vacuum_threshold'\'') + (SELECT setting::float FROM pg_settings WHERE name = '\''autovacuum_vacuum_scale_factor'\'') * n_live_tup as vacuum_threshold FROM pg_stat_user_tables WHERE n_dead_tup > 1000 ORDER BY n_dead_tup DESC LIMIT 10;"'
```

#### IF XID age > 100M

```bash
# Check autovacuum freeze settings
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT name, setting FROM pg_settings WHERE name LIKE '\''%freeze%'\'' OR name = '\''autovacuum_freeze_max_age'\'';"'

# Check oldest transaction
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT datname, datfrozenxid, age(datfrozenxid) FROM pg_database ORDER BY age(datfrozenxid) DESC;"'

# Check tables needing freeze
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT relname, age(relfrozenxid) as xid_age FROM pg_class WHERE relkind = '\''r'\'' ORDER BY age(relfrozenxid) DESC LIMIT 10;"'
```

#### IF unused indexes found

```bash
# Verify indexes are truly unused (check over time, not just since stats reset)
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT stats_reset FROM pg_stat_user_indexes LIMIT 1;"'

# Check if these are primary keys or unique constraints (cannot drop)
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT i.relname as index_name, c.contype, c.conname FROM pg_stat_user_indexes s JOIN pg_class i ON s.indexrelid = i.oid LEFT JOIN pg_constraint c ON c.conindid = i.oid WHERE s.idx_scan = 0 ORDER BY pg_relation_size(s.indexrelid) DESC LIMIT 15;"'

# Check index definition
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT indexrelname, pg_get_indexdef(indexrelid) FROM pg_stat_user_indexes WHERE idx_scan = 0 ORDER BY pg_relation_size(indexrelid) DESC LIMIT 10;"'
```

#### IF connection usage > 70%

```bash
# Check connections by application/user
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT usename, application_name, client_addr, count(*) FROM pg_stat_activity GROUP BY usename, application_name, client_addr ORDER BY count DESC;"'

# Check idle connections
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT state, count(*), max(now() - state_change) as max_idle_time FROM pg_stat_activity GROUP BY state;"'

# Check for connection leaks (very old idle connections)
railway ssh --project <p> --service <s> --environment <e> -- \
  'PAGER=cat psql $DATABASE_URL -c "SELECT pid, usename, application_name, state, backend_start, state_change FROM pg_stat_activity WHERE state = '\''idle'\'' AND state_change < now() - interval '\''1 hour'\'' ORDER BY state_change LIMIT 20;"'
```

### Step 5: Postgres HA (Patroni) - if applicable

```bash
# Full cluster status
railway ssh --project <p> --service <s> --environment <e> -- 'curl -s localhost:8008/cluster'

# Node health
railway ssh --project <p> --service <s> --environment <e> -- 'curl -s localhost:8008/health'

# Timeline check
railway ssh --project <p> --service <s> --environment <e> -- \
  'curl -s localhost:8008/cluster | jq ".members[] | {name, role, state, timeline, lag}"'

# Patroni config
railway ssh --project <p> --service <s> --environment <e> -- 'curl -s localhost:8008/config'

# Failover history
railway ssh --project <p> --service <s> --environment <e> -- 'curl -s localhost:8008/history'
```

### Redis Analysis

```bash
# Memory
railway ssh --project <p> --service <s> --environment <e> -- \
  'redis-cli INFO memory'

# Clients
railway ssh --project <p> --service <s> --environment <e> -- 'redis-cli INFO clients'

# Stats
railway ssh --project <p> --service <s> --environment <e> -- 'redis-cli INFO stats'

# Keyspace
railway ssh --project <p> --service <s> --environment <e> -- 'redis-cli INFO keyspace'

# Slowlog
railway ssh --project <p> --service <s> --environment <e> -- 'redis-cli SLOWLOG GET 20'

# Replication
railway ssh --project <p> --service <s> --environment <e> -- 'redis-cli INFO replication'

# Persistence
railway ssh --project <p> --service <s> --environment <e> -- 'redis-cli INFO persistence'

# IF memory fragmentation > 1.5
railway ssh --project <p> --service <s> --environment <e> -- 'redis-cli MEMORY DOCTOR'
railway ssh --project <p> --service <s> --environment <e> -- 'redis-cli INFO memory | grep -E "mem_fragmentation|allocator"'
```

### MySQL Analysis

```bash
# Connections
railway ssh --project <p> --service <s> --environment <e> -- \
  'mysql -e "SELECT user, host, count(*) FROM information_schema.processlist GROUP BY user, host;"'

# Long queries
railway ssh --project <p> --service <s> --environment <e> -- \
  'mysql -e "SELECT id, user, time, state, LEFT(info, 60) FROM information_schema.processlist WHERE time > 5;"'

# Database sizes
railway ssh --project <p> --service <s> --environment <e> -- \
  'mysql -e "SELECT table_schema, ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb FROM information_schema.tables GROUP BY table_schema ORDER BY size_mb DESC;"'

# Buffer pool
railway ssh --project <p> --service <s> --environment <e> -- \
  'mysql -e "SHOW STATUS LIKE '\''Innodb_buffer_pool%'\'';"'

# Replication
railway ssh --project <p> --service <s> --environment <e> -- 'mysql -e "SHOW SLAVE STATUS\G"'
```

### MongoDB Analysis

```bash
# Server status
railway ssh --project <p> --service <s> --environment <e> -- \
  'mongosh --quiet --eval "JSON.stringify(db.serverStatus().connections)"'

# Current ops
railway ssh --project <p> --service <s> --environment <e> -- \
  'mongosh --quiet --eval "db.currentOp().inprog.length"'

# Long ops
railway ssh --project <p> --service <s> --environment <e> -- \
  'mongosh --quiet --eval "db.currentOp({secs_running: {\$gt: 5}}).inprog"'

# DB stats
railway ssh --project <p> --service <s> --environment <e> -- \
  'mongosh --quiet --eval "JSON.stringify(db.stats())"'

# Replica status
railway ssh --project <p> --service <s> --environment <e> -- \
  'mongosh --quiet --eval "try { rs.status() } catch(e) { \"standalone\" }"'
```

### Thresholds Reference

| Category | Metric | OK | WARNING | CRITICAL |
|----------|--------|-----|---------|----------|
| Cache | Table hit ratio | >99% | 95-99% | <95% |
| Cache | Index hit ratio | >99% | 95-99% | <95% |
| Connections | Usage % | <70% | 70-90% | >90% |
| Vacuum | Dead rows % | <5% | 5-20% | >20% |
| Vacuum | XID age | <100M | 100-150M | >150M |
| Replication | Lag | <1s | 1-10s | >10s |
| Memory | Usage % | <80% | 80-90% | >90% |
| Disk | Usage % | <70% | 70-85% | >85% |
| Redis | Fragmentation | <1.5 | 1.5-2.0 | >2.0 |

### Summary Report Format

After ALL checks complete, provide:

1. **Overview**: Service name, DB type, deployment status
2. **Resources**: Memory, disk, CPU with status
3. **Core Metrics**: All metrics with OK/WARN/CRIT status
4. **Issues Found**: List each warning/critical with:
   - What the metric shows
   - Deep investigation results
   - Root cause analysis
   - Specific recommendation (only if root cause is clear)
5. **No Action Needed**: If investigation shows metric is actually fine

**NEVER recommend action without completing deep investigation first.**
