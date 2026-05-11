#!/bin/bash
# Auto-approve railway-api.sh and railway CLI commands

input=$(cat)

tool_name=$(echo "$input" | jq -r '.tool_name // empty')
command=$(echo "$input" | jq -r '.tool_input.command // empty')

if [[ "$tool_name" != "Bash" ]]; then
  exit 0
fi

# Auto-approve railway-api.sh calls
if [[ "$command" == *"railway-api.sh"* ]]; then
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Railway API call auto-approved"
  }
}
EOF
  exit 0
fi

# Auto-approve railway CLI commands, including skill telemetry env prefixes.
railway_cli_pattern="^[[:space:]]*((RAILWAY_CALLER|RAILWAY_AGENT_SESSION|RAILWAY_SKILL_VERSION)=([^[:space:]\"']+|\"[^\"]*\"|'[^']*')[[:space:]]+)*railway([[:space:]]|$)"
if [[ "$command" =~ $railway_cli_pattern ]]; then
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Railway CLI command auto-approved"
  }
}
EOF
  exit 0
fi

exit 0
