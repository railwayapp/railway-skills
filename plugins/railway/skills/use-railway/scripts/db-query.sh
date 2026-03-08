#!/usr/bin/env bash
# Safe database query wrapper for Railway services
# Handles SSH complexity, escaping, and pager issues automatically
#
# Usage:
#   db-query.sh --service <name> --type postgres --query "SELECT 1;"
#   db-query.sh --service <name> --type postgres --preset connections
#   db-query.sh --domain <domain> --type redis --query "INFO memory"
#
# Supports: postgres, redis, mysql, mongodb

set -euo pipefail

# Defaults
SERVICE=""
DOMAIN=""
DB_TYPE=""
QUERY=""
PRESET=""
RAW_OUTPUT=false
TIMEOUT=30

# Preset queries for common analysis tasks
declare -A POSTGRES_PRESETS=(
  ["connections"]="SELECT state, count(*) FROM pg_stat_activity GROUP BY state ORDER BY count DESC"
  ["connection_pool"]="SELECT (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as current_connections, (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections"
  ["db_sizes"]="SELECT datname, pg_size_pretty(pg_database_size(datname)) as size FROM pg_database ORDER BY pg_database_size(datname) DESC LIMIT 5"
  ["table_sizes"]="SELECT relname AS table_name, pg_size_pretty(pg_total_relation_size(relid)) AS total_size FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 15"
  ["cache_hit"]="SELECT ROUND(100.0 * sum(heap_blks_hit) / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) as table_cache_hit_pct, ROUND(100.0 * sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0), 2) as index_cache_hit_pct FROM pg_statio_user_tables"
  ["cache_per_table"]="SELECT relname as table_name, heap_blks_read as disk_reads, heap_blks_hit as cache_hits, ROUND(100.0 * heap_blks_hit / NULLIF(heap_blks_hit + heap_blks_read, 0), 2) as hit_pct FROM pg_statio_user_tables WHERE heap_blks_read + heap_blks_hit > 1000 ORDER BY heap_blks_read DESC LIMIT 15"
  ["memory_settings"]="SELECT name, setting, unit FROM pg_settings WHERE name IN ('shared_buffers', 'effective_cache_size', 'work_mem', 'maintenance_work_mem', 'max_connections')"
  ["vacuum_health"]="SELECT schemaname, relname as table_name, n_live_tup as live_rows, n_dead_tup as dead_rows, CASE WHEN n_live_tup > 0 THEN ROUND(100.0 * n_dead_tup / n_live_tup, 2) ELSE 0 END as dead_pct, last_autovacuum::date, last_vacuum::date FROM pg_stat_user_tables WHERE n_dead_tup > 100 ORDER BY n_dead_tup DESC LIMIT 15"
  ["xid_age"]="SELECT datname, age(datfrozenxid) as xid_age FROM pg_database WHERE datname = current_database()"
  ["top_queries"]="SELECT left(query, 80) as query, calls, ROUND(total_exec_time::numeric/1000/60, 1) as total_min, ROUND(mean_exec_time::numeric, 1) as mean_ms FROM pg_stat_statements s JOIN pg_database d ON s.dbid = d.oid WHERE d.datname = current_database() ORDER BY total_exec_time DESC LIMIT 12"
  ["long_queries"]="SELECT pid, now() - pg_stat_activity.query_start AS duration, left(query, 60) as query FROM pg_stat_activity WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 seconds' ORDER BY duration DESC"
  ["locks"]="SELECT l.locktype, l.mode, a.usename, left(a.query, 50) as query FROM pg_locks l JOIN pg_stat_activity a ON l.pid = a.pid WHERE a.datname = current_database() AND NOT l.granted LIMIT 10"
  ["unused_indexes"]="SELECT s.relname as table_name, s.indexrelname as index_name, pg_size_pretty(pg_relation_size(s.indexrelid)) as index_size, s.idx_scan as scans FROM pg_stat_user_indexes s WHERE s.idx_scan = 0 AND pg_relation_size(s.indexrelid) > 8192 ORDER BY pg_relation_size(s.indexrelid) DESC LIMIT 15"
  ["seq_scans"]="SELECT relname as table_name, seq_scan, idx_scan, n_live_tup as rows FROM pg_stat_user_tables WHERE seq_scan > 100 AND n_live_tup > 1000 ORDER BY seq_scan DESC LIMIT 10"
  ["replication"]="SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn FROM pg_stat_replication"
)

declare -A REDIS_PRESETS=(
  ["info"]="INFO"
  ["memory"]="INFO memory"
  ["clients"]="INFO clients"
  ["replication"]="INFO replication"
  ["keyspace"]="INFO keyspace"
  ["slowlog"]="SLOWLOG GET 10"
  ["persistence"]="INFO persistence"
)

declare -A MYSQL_PRESETS=(
  ["processlist"]="SHOW PROCESSLIST"
  ["status"]="SHOW STATUS"
  ["buffer_pool"]="SHOW STATUS LIKE 'Innodb_buffer_pool%'"
  ["connections"]="SELECT user, host, count(*) as conns FROM information_schema.processlist GROUP BY user, host"
  ["db_sizes"]="SELECT table_schema AS database_name, ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb FROM information_schema.tables GROUP BY table_schema ORDER BY size_mb DESC"
  ["table_sizes"]="SELECT table_name, ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY size_mb DESC LIMIT 20"
)

declare -A MONGODB_PRESETS=(
  ["status"]="db.serverStatus()"
  ["connections"]="db.serverStatus().connections"
  ["current_ops"]="db.currentOp()"
  ["stats"]="db.stats()"
  ["rs_status"]="rs.status()"
)

# Destructive keywords to block
DESTRUCTIVE_KEYWORDS="DELETE|DROP|TRUNCATE|UPDATE|INSERT|ALTER|CREATE|GRANT|REVOKE|FLUSHALL|FLUSHDB|SHUTDOWN|SLAVEOF|REPLICAOF|CONFIG SET"

usage() {
  cat <<EOF
Usage: db-query.sh [OPTIONS]

Query Railway database services safely via SSH.

Options:
  --service <name>     Service name (requires linked project)
  --domain <domain>    Service domain (e.g., myapp.up.railway.app)
  --type <type>        Database type: postgres, redis, mysql, mongodb
  --query <sql>        Custom query to execute
  --preset <name>      Use a preset query (see --list-presets)
  --raw                Output raw results without formatting
  --timeout <sec>      SSH timeout in seconds (default: 30)
  --list-presets       List available preset queries
  --help               Show this help

Examples:
  # Using service name (requires: railway link)
  db-query.sh --service core-postgres --type postgres --preset connections
  db-query.sh --service core-postgres --type postgres --query "SELECT count(*) FROM users;"

  # Using domain (no linking required)
  db-query.sh --domain mydb.up.railway.app --type postgres --preset cache_hit

  # Redis
  db-query.sh --service my-redis --type redis --preset memory

Presets (postgres):
  connections, connection_pool, db_sizes, table_sizes, cache_hit, cache_per_table,
  memory_settings, vacuum_health, xid_age, top_queries, long_queries, locks,
  unused_indexes, seq_scans, replication

Presets (redis):
  info, memory, clients, replication, keyspace, slowlog, persistence

Presets (mysql):
  processlist, status, buffer_pool, connections, db_sizes, table_sizes

Presets (mongodb):
  status, connections, current_ops, stats, rs_status
EOF
  exit 0
}

list_presets() {
  echo "Available presets:"
  echo ""
  echo "=== postgres ==="
  for key in "${!POSTGRES_PRESETS[@]}"; do
    echo "  $key"
  done | sort
  echo ""
  echo "=== redis ==="
  for key in "${!REDIS_PRESETS[@]}"; do
    echo "  $key"
  done | sort
  echo ""
  echo "=== mysql ==="
  for key in "${!MYSQL_PRESETS[@]}"; do
    echo "  $key"
  done | sort
  echo ""
  echo "=== mongodb ==="
  for key in "${!MONGODB_PRESETS[@]}"; do
    echo "  $key"
  done | sort
  exit 0
}

error() {
  echo "Error: $1" >&2
  exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE="$2"
      shift 2
      ;;
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --type)
      DB_TYPE="$2"
      shift 2
      ;;
    --query)
      QUERY="$2"
      shift 2
      ;;
    --preset)
      PRESET="$2"
      shift 2
      ;;
    --raw)
      RAW_OUTPUT=true
      shift
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    --list-presets)
      list_presets
      ;;
    --help|-h)
      usage
      ;;
    *)
      error "Unknown option: $1"
      ;;
  esac
done

# Validate required arguments
if [[ -z "$SERVICE" && -z "$DOMAIN" ]]; then
  error "Either --service or --domain is required"
fi

if [[ -z "$DB_TYPE" ]]; then
  error "--type is required (postgres, redis, mysql, mongodb)"
fi

if [[ -z "$QUERY" && -z "$PRESET" ]]; then
  error "Either --query or --preset is required"
fi

# Validate db-type
case "$DB_TYPE" in
  postgres|redis|mysql|mongodb) ;;
  *)
    error "Unsupported --type: $DB_TYPE. Use: postgres, redis, mysql, mongodb"
    ;;
esac

# Resolve preset to query
if [[ -n "$PRESET" ]]; then
  case "$DB_TYPE" in
    postgres)
      QUERY="${POSTGRES_PRESETS[$PRESET]:-}"
      ;;
    redis)
      QUERY="${REDIS_PRESETS[$PRESET]:-}"
      ;;
    mysql)
      QUERY="${MYSQL_PRESETS[$PRESET]:-}"
      ;;
    mongodb)
      QUERY="${MONGODB_PRESETS[$PRESET]:-}"
      ;;
  esac

  if [[ -z "$QUERY" ]]; then
    error "Unknown preset '$PRESET' for type '$DB_TYPE'. Use --list-presets to see available presets."
  fi
fi

# Check for destructive keywords (case-insensitive)
QUERY_UPPER=$(echo "$QUERY" | tr '[:lower:]' '[:upper:]')
if echo "$QUERY_UPPER" | grep -qE "$DESTRUCTIVE_KEYWORDS"; then
  error "Query contains destructive keyword. Blocked for safety. Run mutations manually via SSH with explicit user confirmation."
fi

# Build SSH command
build_ssh_command() {
  local cmd="$1"

  if [[ -n "$SERVICE" ]]; then
    # Use railway CLI SSH (requires linked project)
    echo "railway ssh --service $SERVICE -- '$cmd'"
  else
    # Use direct SSH
    echo "ssh -o ConnectTimeout=$TIMEOUT ${DOMAIN}@ssh.railway.com \"$cmd\""
  fi
}

# Execute query based on db-type
case "$DB_TYPE" in
  postgres)
    # Build psql command with pager disabled and read-only mode
    PSQL_CMD="PAGER='' psql \$DATABASE_URL -P pager=off -c \"SET default_transaction_read_only = on; $QUERY\""

    if [[ -n "$SERVICE" ]]; then
      # Escape for railway ssh
      railway ssh --service "$SERVICE" -- "PAGER='' psql \$DATABASE_URL -P pager=off -c \"SET default_transaction_read_only = on; $QUERY\""
    else
      ssh -o ConnectTimeout="$TIMEOUT" "${DOMAIN}@ssh.railway.com" "PAGER='' psql \$DATABASE_URL -P pager=off -c \"SET default_transaction_read_only = on; $QUERY\""
    fi
    ;;

  redis)
    if [[ -n "$SERVICE" ]]; then
      railway ssh --service "$SERVICE" -- "redis-cli $QUERY"
    else
      ssh -o ConnectTimeout="$TIMEOUT" "${DOMAIN}@ssh.railway.com" "redis-cli $QUERY"
    fi
    ;;

  mysql)
    if [[ -n "$SERVICE" ]]; then
      railway ssh --service "$SERVICE" -- "mysql -e 'SET SESSION TRANSACTION READ ONLY; $QUERY'"
    else
      ssh -o ConnectTimeout="$TIMEOUT" "${DOMAIN}@ssh.railway.com" "mysql -e 'SET SESSION TRANSACTION READ ONLY; $QUERY'"
    fi
    ;;

  mongodb)
    if [[ -n "$SERVICE" ]]; then
      railway ssh --service "$SERVICE" -- "mongosh --quiet --eval 'db.getMongo().setReadPref(\"secondary\"); $QUERY'"
    else
      ssh -o ConnectTimeout="$TIMEOUT" "${DOMAIN}@ssh.railway.com" "mongosh --quiet --eval 'db.getMongo().setReadPref(\"secondary\"); $QUERY'"
    fi
    ;;
esac
