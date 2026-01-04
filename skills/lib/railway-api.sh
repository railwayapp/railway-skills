#!/usr/bin/env bash
# Railway GraphQL API helper
# Usage: railway-api.sh '<graphql-query>'

set -e

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

# Use jq to properly escape the query for JSON
PAYLOAD=$(jq -n --arg q "$1" '{query: $q}')

curl -s https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
