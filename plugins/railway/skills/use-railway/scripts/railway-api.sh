#!/usr/bin/env bash
# Railway GraphQL API helper
# Usage: railway-api.sh '<graphql-query>' ['<variables-json>']

set -e

SKILL_ID="use-railway"
SKILL_VERSION="${RAILWAY_SKILL_VERSION:-1.2.3}"

export RAILWAY_CALLER="${RAILWAY_CALLER:-skill:${SKILL_ID}@${SKILL_VERSION}}"
export RAILWAY_AGENT_SESSION="${RAILWAY_AGENT_SESSION:-railway-skill-$(date +%s)-$$}"

if ! command -v jq &>/dev/null; then
  echo '{"error": "jq not installed. Install with: brew install jq"}'
  exit 1
fi

CONFIG_FILE="$HOME/.railway/config.json"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo '{"error": "Railway config not found. Run: railway login"}'
  exit 1
fi

# Browser login stores the session under .user.accessToken; .user.token is a legacy field that
# current CLI releases leave unset. Prefer the current one, and keep reading the legacy one so
# older configs continue to work.
TOKEN=$(jq -r '.user.accessToken // .user.token // empty' "$CONFIG_FILE")

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo '{"error": "No Railway token found. Run: railway login"}'
  exit 1
fi

# The access token is short-lived and the CLI owns refreshing it, so this helper must not. Without
# this check an expired token reaches the API and returns a bare "Not Authorized", which reads as a
# permissions problem rather than a stale session.
EXPIRES_AT=$(jq -r '.user.tokenExpiresAt // empty' "$CONFIG_FILE")
if [[ "$EXPIRES_AT" =~ ^[0-9]+$ ]] && (( EXPIRES_AT <= $(date +%s) )); then
  echo '{"error": "Railway token expired. Run any railway command to refresh it, or: railway login"}'
  exit 1
fi

if [[ -z "$1" ]]; then
  echo '{"error": "No query provided"}'
  exit 1
fi

# Build payload with query and optional variables
if [[ -n "$2" ]]; then
  PAYLOAD=$(jq -n --arg q "$1" --argjson v "$2" '{query: $q, variables: $v}')
else
  PAYLOAD=$(jq -n --arg q "$1" '{query: $q}')
fi

HEADERS=(
  -H "Content-Type: application/json"
  -H "X-Railway-Skill-Id: $SKILL_ID"
  -H "X-Railway-Skill-Version: $SKILL_VERSION"
  -H "X-Railway-Agent-Session: $RAILWAY_AGENT_SESSION"
)

# Keep the token and the request body out of argv: /proc/<pid>/cmdline is
# readable by any other local user, so anything passed as an argument leaks on a
# shared host. The bearer goes in through --config on a pipe, the payload on stdin.
printf '%s' "$PAYLOAD" | curl -s https://backboard.railway.com/graphql/v2 \
  "${HEADERS[@]}" \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$TOKEN") \
  -d @-
