#!/usr/bin/env bash
# Railway GraphQL API helper
# Usage: railway-api.sh '<graphql-query>' ['<variables-json>']

set -e

SKILL_ID="use-railway"
SKILL_VERSION="${RAILWAY_SKILL_VERSION:-1.2.1}"

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

TOKEN=$(jq -r '.user.token' "$CONFIG_FILE")

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo '{"error": "No Railway token found. Run: railway login"}'
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
  -H "Authorization: Bearer $TOKEN"
  -H "Content-Type: application/json"
  -H "X-Railway-Skill-Id: $SKILL_ID"
  -H "X-Railway-Skill-Version: $SKILL_VERSION"
  -H "X-Railway-Agent-Session: $RAILWAY_AGENT_SESSION"
)

curl -s https://backboard.railway.com/graphql/v2 "${HEADERS[@]}" -d "$PAYLOAD"
