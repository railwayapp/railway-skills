# SSH

SSH into services and query databases directly. Use this for database introspection, debugging inside containers, or accessing metrics not exposed via the Railway API.

## SSH formats

### Direct SSH (preferred)

```bash
ssh <domain>@ssh.railway.com
```

Where `<domain>` is the service's Railway domain (e.g., `myapp.up.railway.app`). This works via TCP proxy with one connection + loopback from the instance.

### Railway CLI SSH

```bash
railway ssh --service <service>
```

This requires a linked project context. Use direct SSH when you know the domain but aren't linked.

## Prerequisites

- **SSH key registered**: The user must have an SSH key added to their Railway account (Settings > SSH Keys)
- **Active deployment**: The service must have a running deployment. SSH does not work on stopped or crashed services.
- **Port listening**: The service must be running (listening on some port). Cron jobs or one-shot containers may not be reachable.

## Database introspection

Use SSH to run database queries directly inside the container. This avoids needing database CLIs installed locally.

### Postgres

```bash
# Connection count by state
ssh <domain>@ssh.railway.com "psql \$DATABASE_URL -c \"SELECT state, count(*) FROM pg_stat_activity GROUP BY state;\""

# Active queries running longer than 5 seconds
ssh <domain>@ssh.railway.com "psql \$DATABASE_URL -c \"SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 seconds';\""

# Database sizes
ssh <domain>@ssh.railway.com "psql \$DATABASE_URL -c \"SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY pg_database_size(datname) DESC;\""

# Table sizes in current database
ssh <domain>@ssh.railway.com "psql \$DATABASE_URL -c \"SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC LIMIT 20;\""

# Replication status (primary)
ssh <domain>@ssh.railway.com "psql \$DATABASE_URL -c \"SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn FROM pg_stat_replication;\""

# Replication lag (replica)
ssh <domain>@ssh.railway.com "psql \$DATABASE_URL -c \"SELECT CASE WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn() THEN 0 ELSE EXTRACT(EPOCH FROM now() - pg_last_xact_replay_timestamp()) END AS lag_seconds;\""
```

### Postgres HA (Patroni)

Postgres HA clusters run Patroni for failover management. Query the Patroni API on localhost:8008:

```bash
# Cluster status (members, roles, lag)
ssh <domain>@ssh.railway.com "curl -s localhost:8008/cluster | jq"

# Current leader
ssh <domain>@ssh.railway.com "curl -s localhost:8008/leader | jq"

# This node's health
ssh <domain>@ssh.railway.com "curl -s localhost:8008/health | jq"

# Replica status
ssh <domain>@ssh.railway.com "curl -s localhost:8008/replica | jq"

# Patroni configuration
ssh <domain>@ssh.railway.com "curl -s localhost:8008/config | jq"

# History (timeline changes, failovers)
ssh <domain>@ssh.railway.com "curl -s localhost:8008/history | jq"
```

Patroni endpoints return JSON with cluster topology, replication lag, and failover history.

### Redis

```bash
# Server info (memory, clients, replication)
ssh <domain>@ssh.railway.com "redis-cli INFO"

# Memory usage summary
ssh <domain>@ssh.railway.com "redis-cli INFO memory"

# Connected clients
ssh <domain>@ssh.railway.com "redis-cli CLIENT LIST"

# Slow queries log
ssh <domain>@ssh.railway.com "redis-cli SLOWLOG GET 10"

# Keyspace statistics
ssh <domain>@ssh.railway.com "redis-cli INFO keyspace"

# Current commands being processed
ssh <domain>@ssh.railway.com "redis-cli MONITOR" # Warning: streams all commands, Ctrl+C to stop
```

### MySQL

```bash
# Active connections and queries
ssh <domain>@ssh.railway.com "mysql -e 'SHOW PROCESSLIST;'"

# Server status variables
ssh <domain>@ssh.railway.com "mysql -e 'SHOW STATUS;'"

# Replication status (replica)
ssh <domain>@ssh.railway.com "mysql -e 'SHOW SLAVE STATUS\\G'"

# Database sizes
ssh <domain>@ssh.railway.com "mysql -e 'SELECT table_schema AS database_name, ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb FROM information_schema.tables GROUP BY table_schema ORDER BY size_mb DESC;'"

# Table sizes
ssh <domain>@ssh.railway.com "mysql -e 'SELECT table_name, ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY size_mb DESC LIMIT 20;'"
```

### MongoDB

```bash
# Server status
ssh <domain>@ssh.railway.com "mongosh --quiet --eval 'db.serverStatus()'"

# Current operations
ssh <domain>@ssh.railway.com "mongosh --quiet --eval 'db.currentOp()'"

# Replica set status
ssh <domain>@ssh.railway.com "mongosh --quiet --eval 'rs.status()'"

# Database stats
ssh <domain>@ssh.railway.com "mongosh --quiet --eval 'db.stats()'"

# Collection stats
ssh <domain>@ssh.railway.com "mongosh --quiet --eval 'db.getCollectionNames().forEach(c => printjson({name: c, stats: db.getCollection(c).stats()}))'"
```

## Resource inspection

Check container resources directly:

```bash
# Memory usage
ssh <domain>@ssh.railway.com "free -h"
ssh <domain>@ssh.railway.com "cat /proc/meminfo | head -5"

# CPU info
ssh <domain>@ssh.railway.com "cat /proc/cpuinfo | grep 'model name' | head -1"
ssh <domain>@ssh.railway.com "uptime"

# Disk usage
ssh <domain>@ssh.railway.com "df -h"

# Running processes
ssh <domain>@ssh.railway.com "ps aux --sort=-%mem | head -10"

# Environment variables (sanitized)
ssh <domain>@ssh.railway.com "env | grep -v PASSWORD | grep -v SECRET | grep -v KEY | sort"
```

## Using the db-query script

For safer database queries, use the wrapper script that blocks destructive operations:

```bash
scripts/db-query.sh <domain> postgres "SELECT count(*) FROM users;"
scripts/db-query.sh <domain> redis "INFO memory"
scripts/db-query.sh <domain> mysql "SHOW PROCESSLIST;"
scripts/db-query.sh <domain> mongodb "db.stats()"
```

The script rejects queries containing destructive keywords (DELETE, DROP, TRUNCATE, UPDATE, FLUSHALL, FLUSHDB).

## Safety guardrails

1. **Read-only by default**: All example queries are SELECT or read operations. Never run mutations without explicit user confirmation.
2. **Confirm destructive actions**: Before any DELETE, DROP, TRUNCATE, UPDATE, or data-modifying operation, state the impact and ask for confirmation.
3. **Avoid MONITOR in Redis**: The MONITOR command streams all commands and can impact performance. Use sparingly and Ctrl+C to stop.
4. **Credential exposure**: Avoid echoing DATABASE_URL or other connection strings. Use env var references (`$DATABASE_URL`) instead of hardcoded values.

## Troubleshooting

### "Permission denied (publickey)"

SSH key not registered with Railway. Guide the user to:
1. Generate a key if needed: `ssh-keygen -t ed25519`
2. Add to Railway: Settings > SSH Keys > Add Key
3. Paste contents of `~/.ssh/id_ed25519.pub`

### "Connection refused" or timeout

- Service may not be running. Check `railway service status --service <service> --json`
- Deployment may have crashed. Check logs: `railway logs --service <service> --lines 50`
- Network issue. Try again or use Railway CLI SSH instead.

### "command not found" (psql, redis-cli, etc.)

The database CLI may not be in the container's PATH or may be named differently. Try:
```bash
ssh <domain>@ssh.railway.com "which psql || find /usr -name 'psql' 2>/dev/null"
```

For Railway-managed databases, the CLIs are pre-installed. For custom images, the user must include them.

### "FATAL: password authentication failed"

The `$DATABASE_URL` may not be set or may be incorrect. Check:
```bash
ssh <domain>@ssh.railway.com "echo \$DATABASE_URL | head -c 50"
```

If empty, the variable reference service may not be configured correctly.

## Validated against

- SSH format confirmed by Railway engineering (Discord, March 2026)
- Patroni API: [Patroni REST API docs](https://patroni.readthedocs.io/en/latest/rest_api.html)
- Postgres system views: [pg_stat_activity](https://www.postgresql.org/docs/current/monitoring-stats.html)
