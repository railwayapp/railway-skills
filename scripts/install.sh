#!/usr/bin/env bash
set -e

REPO="https://github.com/railwayapp/railway-skills"

# ANSI colors
BOLD=$'\033[1m'
GREY=$'\033[90m'
RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
MAGENTA=$'\033[35m'
CYAN=$'\033[36m'
NC=$'\033[0m'

info() { printf "${BOLD}${GREY}>${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}! %s${NC}\n" "$*"; }
error() { printf "${RED}x %s${NC}\n" "$*" >&2; }
completed() { printf "${GREEN}✓${NC} %s\n" "$*"; }

print_success() {
  printf "${MAGENTA}"
  cat <<'EOF'
                   .
         /^\     .
    /\   "V"
   /__\   I      O  o
  //..\\  I     .                             Poof!
  \].`[/  I
  /l\/j\  (]    .  O
 /. ~~ ,\/I          .            Skills installed successfully!
 \\L__j^\/I       o
  \/--v}  I     o   .
  |    |  I   _________
  |    |  I c(`       ')o
  |    l  I   \.     ,/
_/j  L l\_!  _//^---^\\_

EOF
  printf "${NC}"
}

install_skills() {
  local skills_dir="$1"
  local name="$2"
  local temp_dir="$3"

  mkdir -p "$skills_dir"
  rm -rf "$skills_dir"/railway-* 2>/dev/null || true

  local count=0
  for d in "$temp_dir"/plugins/railway/skills/*/; do
    skill_name=$(basename "$d")
    [[ "$skill_name" == _* ]] && continue
    [ -f "$d/SKILL.md" ] || continue
    cp -R "$d" "$skills_dir/railway-$skill_name"
    count=$((count + 1))
  done

  completed "$name: ${GREEN}$count${NC} skills → ${CYAN}$skills_dir${NC}"
}

# Targets: [dir, name]
declare -a TARGETS=(
  "$HOME/.claude/skills|Claude Code"
  "$HOME/.codex/skills|OpenAI Codex"
  "$HOME/.config/opencode/skill|OpenCode"
  "$HOME/.cursor/skills|Cursor"
)

# Detect available tools
declare -a FOUND=()
for target in "${TARGETS[@]}"; do
  dir="${target%%|*}"
  parent="${dir%/*}"
  [ -d "$parent" ] && FOUND+=("$target")
done

if [ ${#FOUND[@]} -eq 0 ]; then
  error "No supported tools found."
  printf "\nSupported:\n"
  printf "  • Claude Code (~/.claude)\n"
  printf "  • OpenAI Codex (~/.codex)\n"
  printf "  • OpenCode (~/.config/opencode)\n"
  printf "  • Cursor (~/.cursor)\n"
  exit 1
fi

printf "\n${BOLD}Railway Skills${NC}\n\n"

info "Downloading from ${CYAN}$REPO${NC}..."
temp_dir=$(mktemp -d)
git clone --depth 1 --quiet "$REPO" "$temp_dir"
printf "\n"

for target in "${FOUND[@]}"; do
  dir="${target%%|*}"
  name="${target##*|}"
  install_skills "$dir" "$name" "$temp_dir"
done

rm -rf "$temp_dir"

printf "\n"
print_success
warn "Restart your tool(s) to load skills."
printf "\n"
info "Re-run anytime to update."
printf "\n"
