#!/usr/bin/env bash
# Shared Railway CLI utilities for Claude plugin skills

check_railway_cli() {
  if command -v railway &>/dev/null; then
    echo '{"installed": true, "path": "'$(which railway)'"}'
    return 0
  else
    echo '{"installed": false, "error": "cli_missing"}'
    return 1
  fi
}

check_railway_auth() {
  local whoami_output
  whoami_output=$(railway whoami --json 2>&1)
  local exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    echo "$whoami_output"
    return 0
  else
    echo '{"authenticated": false, "error": "not_authenticated"}'
    return 1
  fi
}

check_railway_linked() {
  local status_output
  status_output=$(railway status --json 2>&1)
  local exit_code=$?

  if [[ $exit_code -eq 0 ]] && [[ "$status_output" != *"No linked project"* ]] && [[ "$status_output" != *"error"* ]]; then
    echo "$status_output"
    return 0
  else
    echo '{"linked": false, "error": "not_linked"}'
    return 1
  fi
}

railway_preflight() {
  # Check CLI installed
  if ! command -v railway &>/dev/null; then
    echo '{"ready": false, "error": "cli_missing"}'
    return 1
  fi

  # Check authenticated
  local auth_check
  auth_check=$(railway whoami --json 2>&1)
  if [[ $? -ne 0 ]]; then
    echo '{"ready": false, "error": "not_authenticated"}'
    return 1
  fi

  # Check project linked
  local status_output
  status_output=$(railway status --json 2>&1)
  if [[ $? -ne 0 ]] || [[ "$status_output" == *"No linked project"* ]]; then
    echo '{"ready": false, "error": "not_linked"}'
    return 1
  fi

  # All checks passed - return status
  echo "$status_output"
  return 0
}
