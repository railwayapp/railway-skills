#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

SKILLS_DIR="plugins/railway/skills"
SHARED_DIR="$SKILLS_DIR/_shared"

echo "Syncing shared files to skills..."

for skill_dir in "$SKILLS_DIR"/*/; do
  skill_name=$(basename "$skill_dir")

  # Skip _shared itself
  [[ "$skill_name" == _* ]] && continue

  # Skip if no SKILL.md (not a skill)
  [[ ! -f "$skill_dir/SKILL.md" ]] && continue

  # Copy scripts (only railway-api.sh to skills that reference it)
  if grep -q "scripts/railway-api.sh" "$skill_dir/SKILL.md" 2>/dev/null; then
    mkdir -p "$skill_dir/scripts"
    cp "$SHARED_DIR/scripts/railway-api.sh" "$skill_dir/scripts/"
  fi

  # Copy ALL references to ALL skills (simpler maintenance)
  mkdir -p "$skill_dir/references"
  cp "$SHARED_DIR/references/"*.md "$skill_dir/references/"

  echo "  ✓ $skill_name"
done

echo "Done."
