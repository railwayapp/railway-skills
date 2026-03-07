#!/usr/bin/env bash
# Safe database query wrapper for Railway services via SSH
# Usage: db-query.sh <domain> <db-type> <query>
#
# Supported db-types: postgres, redis, mysql, mongodb
# Rejects destructive keywords for safety.

set -e

DOMAIN="$1"
DB_TYPE="$2"
QUERY="$3"

# Destructive keywords to block (case-insensitive check)
DESTRUCTIVE_KEYWORDS="DELETE|DROP|TRUNCATE|UPDATE|INSERT|ALTER|CREATE|FLUSHALL|FLUSHDB|SHUTDOWN|SLAVEOF|REPLICAOF|CONFIG SET"

usage() {
  echo "Usage: db-query.sh <domain> <db-type> <query>"
  echo ""
  echo "Arguments:"
  echo "  domain   Railway service domain (e.g., myapp.up.railway.app)"
  echo "  db-type  Database type: postgres, redis, mysql, mongodb"
  echo "  query    SQL/command to execute (read-only operations only)"
  echo ""
  echo "Examples:"
  echo "  db-query.sh mydb.up.railway.app postgres \"SELECT count(*) FROM users;\""
  echo "  db-query.sh myredis.up.railway.app redis \"INFO memory\""
  echo "  db-query.sh mydb.up.railway.app mysql \"SHOW PROCESSLIST;\""
  echo "  db-query.sh mydb.up.railway.app mongodb \"db.stats()\""
  exit 1
}

error() {
  echo "Error: $1" >&2
  exit 1
}

# Validate arguments
if [[ -z "$DOMAIN" ]]; then
  error "Missing domain argument"
  usage
fi

if [[ -z "$DB_TYPE" ]]; then
  error "Missing db-type argument"
  usage
fi

if [[ -z "$QUERY" ]]; then
  error "Missing query argument"
  usage
fi

# Validate db-type
case "$DB_TYPE" in
  postgres|redis|mysql|mongodb) ;;
  *)
    error "Unsupported db-type: $DB_TYPE. Use: postgres, redis, mysql, mongodb"
    ;;
esac

# Check for destructive keywords (case-insensitive)
QUERY_UPPER=$(echo "$QUERY" | tr '[:lower:]' '[:upper:]')
if echo "$QUERY_UPPER" | grep -qE "$DESTRUCTIVE_KEYWORDS"; then
  error "Query contains destructive keyword. Blocked for safety. Use SSH directly for mutations after confirming with the user."
fi

# Build and execute the SSH command based on db-type
case "$DB_TYPE" in
  postgres)
    ssh "${DOMAIN}@ssh.railway.com" "psql \$DATABASE_URL -c \"$QUERY\""
    ;;
  redis)
    ssh "${DOMAIN}@ssh.railway.com" "redis-cli $QUERY"
    ;;
  mysql)
    ssh "${DOMAIN}@ssh.railway.com" "mysql -e '$QUERY'"
    ;;
  mongodb)
    ssh "${DOMAIN}@ssh.railway.com" "mongosh --quiet --eval '$QUERY'"
    ;;
esac
