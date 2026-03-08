#!/usr/bin/env bash
# Complete database analysis for Railway deployments
# Produces a comprehensive report matching the format used by the analyze-db skill
#
# Usage:
#   analyze-db.sh --service <name> --type postgres
#   analyze-db.sh --service <name> --type postgres --deep
#   analyze-db.sh --service <name> --type postgres --json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults
SERVICE=""
DB_TYPE=""
DEEP_ANALYSIS=false
JSON_OUTPUT=false

usage() {
  cat <<EOF
Usage: analyze-db.sh --service <name> --type <db-type> [OPTIONS]

Complete database analysis for Railway services.

Options:
  --service <name>    Database service name (required)
  --type <type>       Database type: postgres, redis, mysql, mongodb (required)
  --deep              Include query stats, index health, detailed analysis
  --json              Output as JSON (for programmatic use)
  -h, --help          Show this help

Examples:
  analyze-db.sh --service core-postgres --type postgres
  analyze-db.sh --service core-postgres --type postgres --deep
  analyze-db.sh --service my-redis --type redis

Requires: railway CLI linked to the project
EOF
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
    --type)
      DB_TYPE="$2"
      shift 2
      ;;
    --deep)
      DEEP_ANALYSIS=true
      shift
      ;;
    --json)
      JSON_OUTPUT=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      error "Unknown option: $1"
      ;;
  esac
done

# Validate arguments
if [[ -z "$SERVICE" ]]; then
  error "--service is required"
fi

if [[ -z "$DB_TYPE" ]]; then
  error "--type is required"
fi

case "$DB_TYPE" in
  postgres|redis|mysql|mongodb) ;;
  *)
    error "Unsupported --type: $DB_TYPE. Use: postgres, redis, mysql, mongodb"
    ;;
esac

# Check railway CLI is available and linked
if ! command -v railway &>/dev/null; then
  error "railway CLI not found. Install with: npm i -g @railway/cli"
fi

# Helper to run db-query with the service
query() {
  local preset_or_query="$1"
  local is_preset="${2:-true}"

  if [[ "$is_preset" == "true" ]]; then
    "$SCRIPT_DIR/db-query.sh" --service "$SERVICE" --type "$DB_TYPE" --preset "$preset_or_query" 2>/dev/null || echo "QUERY_FAILED"
  else
    "$SCRIPT_DIR/db-query.sh" --service "$SERVICE" --type "$DB_TYPE" --query "$preset_or_query" 2>/dev/null || echo "QUERY_FAILED"
  fi
}

# Helper to run SSH commands directly
ssh_cmd() {
  local cmd="$1"
  railway ssh --service "$SERVICE" -- "$cmd" 2>/dev/null || echo "SSH_FAILED"
}

echo "========================================"
echo "Database Analysis: $SERVICE"
echo "========================================"
echo "Type: $DB_TYPE"
echo "Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# ========================================
# Section 1: Deployment Status
# ========================================
echo "## Deployment Status"
echo ""

SERVICE_STATUS=$(railway service status --service "$SERVICE" --json 2>/dev/null || echo '{"status":"UNKNOWN"}')
STATUS=$(echo "$SERVICE_STATUS" | jq -r '.status // "UNKNOWN"')
STOPPED=$(echo "$SERVICE_STATUS" | jq -r '.stopped // false')

echo "Status: $STATUS"
echo "Stopped: $STOPPED"

if [[ "$STATUS" != "SUCCESS" ]] || [[ "$STOPPED" == "true" ]]; then
  echo ""
  echo "WARNING: Service is not running. Analysis may fail."
fi
echo ""

# ========================================
# Section 2: Resource Overview
# ========================================
echo "## Resource Overview"
echo ""

# Disk usage
echo "### Disk"
DISK_OUTPUT=$(ssh_cmd 'df -h /var/lib/postgresql/data 2>/dev/null || df -h / | tail -1')
if [[ "$DISK_OUTPUT" != "SSH_FAILED" ]]; then
  echo "$DISK_OUTPUT" | tail -1
else
  echo "Could not get disk info"
fi
echo ""

# Database-specific analysis
case "$DB_TYPE" in
  postgres)
    # ========================================
    # Postgres Analysis
    # ========================================

    echo "### Connections"
    query "connection_pool"
    echo ""

    echo "### Connection States"
    query "connections"
    echo ""

    echo "### Database Sizes"
    query "db_sizes"
    echo ""

    # ========================================
    # Section 3: Memory Configuration
    # ========================================
    echo "## Memory Configuration"
    echo ""
    query "memory_settings"
    echo ""

    # ========================================
    # Section 4: Cache Efficiency
    # ========================================
    echo "## Cache Efficiency"
    echo ""

    echo "### Overall Cache Hit Ratio"
    query "cache_hit"
    echo ""

    echo "### Per-Table Cache Hit Rates"
    query "cache_per_table"
    echo ""

    echo "### Table Sizes (Working Set)"
    query "table_sizes"
    echo ""

    # ========================================
    # Section 5: Vacuum Health
    # ========================================
    echo "## Vacuum Health"
    echo ""

    echo "### Dead Rows and Autovacuum Status"
    query "vacuum_health"
    echo ""

    echo "### XID Age"
    query "xid_age"
    echo ""

    # ========================================
    # Section 6: Index Health
    # ========================================
    echo "## Index Health"
    echo ""

    echo "### Unused Indexes"
    query "unused_indexes"
    echo ""

    echo "### Sequential Scan Patterns"
    query "seq_scans"
    echo ""

    # ========================================
    # Deep Analysis (if requested)
    # ========================================
    if [[ "$DEEP_ANALYSIS" == "true" ]]; then
      echo "## Query Performance"
      echo ""

      echo "### Top Queries by Execution Time"
      query "top_queries"
      echo ""

      echo "### Long-Running Active Queries"
      query "long_queries"
      echo ""

      echo "### Lock Contention"
      query "locks"
      echo ""

      echo "### Replication Status"
      query "replication"
      echo ""

      # Check for HA cluster (Patroni)
      echo "## HA Cluster Status"
      echo ""
      PATRONI_STATUS=$(ssh_cmd 'curl -s localhost:8008/cluster 2>/dev/null || echo "{}"')
      if [[ "$PATRONI_STATUS" != "SSH_FAILED" ]] && [[ "$PATRONI_STATUS" != "{}" ]]; then
        echo "### Patroni Cluster Members"
        echo "$PATRONI_STATUS" | jq '.members[] | {name, role, state, timeline, lag}' 2>/dev/null || echo "Could not parse Patroni status"
      else
        echo "Not an HA cluster (no Patroni detected)"
      fi
      echo ""
    fi
    ;;

  redis)
    # ========================================
    # Redis Analysis
    # ========================================

    echo "### Memory"
    query "memory"
    echo ""

    echo "### Keyspace"
    query "keyspace"
    echo ""

    echo "### Clients"
    query "clients"
    echo ""

    if [[ "$DEEP_ANALYSIS" == "true" ]]; then
      echo "### Slow Log"
      query "slowlog"
      echo ""

      echo "### Replication"
      query "replication"
      echo ""

      echo "### Persistence"
      query "persistence"
      echo ""
    fi
    ;;

  mysql)
    # ========================================
    # MySQL Analysis
    # ========================================

    echo "### Connections"
    query "connections"
    echo ""

    echo "### Database Sizes"
    query "db_sizes"
    echo ""

    echo "### Table Sizes"
    query "table_sizes"
    echo ""

    if [[ "$DEEP_ANALYSIS" == "true" ]]; then
      echo "### Process List"
      query "processlist"
      echo ""

      echo "### Buffer Pool"
      query "buffer_pool"
      echo ""
    fi
    ;;

  mongodb)
    # ========================================
    # MongoDB Analysis
    # ========================================

    echo "### Connections"
    query "connections"
    echo ""

    echo "### Database Stats"
    query "stats"
    echo ""

    if [[ "$DEEP_ANALYSIS" == "true" ]]; then
      echo "### Current Operations"
      query "current_ops"
      echo ""

      echo "### Replica Set Status"
      query "rs_status"
      echo ""
    fi
    ;;
esac

# ========================================
# Recent Errors
# ========================================
echo "## Recent Errors"
echo ""
ERROR_LOGS=$(railway logs --service "$SERVICE" --lines 50 --filter "@level:error" 2>/dev/null | head -20 || echo "")
if [[ -n "$ERROR_LOGS" ]]; then
  echo "$ERROR_LOGS"
else
  echo "No recent errors in logs"
fi
echo ""

echo "========================================"
echo "END OF REPORT"
echo "========================================"
