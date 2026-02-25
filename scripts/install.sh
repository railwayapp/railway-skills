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

install_skill() {
  local skills_dir="$1"
  local name="$2"
  local temp_dir="$3"
  local source_dir="$temp_dir/plugins/railway/skills/use-railway"
  local target_dir="$skills_dir/use-railway"

  mkdir -p "$skills_dir"

  # Remove legacy skills from previous multi-skill installs
  for old_skill in "$skills_dir"/railway-*/; do
    [ -d "$old_skill" ] && rm -rf "$old_skill"
  done

  if [ ! -f "$source_dir/SKILL.md" ]; then
    error "use-railway skill not found in downloaded repository."
    return 1
  fi

  rm -rf "$target_dir"
  cp -R "$source_dir" "$target_dir"

  completed "$name: installed ${GREEN}use-railway${NC} → ${CYAN}$target_dir${NC}"
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
  install_skill "$dir" "$name" "$temp_dir"
done

# Local installs (skip if CWD is $HOME)
if [ "$(pwd)" != "$HOME" ]; then
  declare -a LOCAL_TARGETS=(
    ".claude/skills|Claude Code (local)"
    ".codex/skills|OpenAI Codex (local)"
    ".config/opencode/skill|OpenCode (local)"
    ".cursor/skills|Cursor (local)"
  )
  for target in "${LOCAL_TARGETS[@]}"; do
    dir="${target%%|*}"
    name="${target##*|}"
    parent="${dir%/*}"
    [ -d "./$parent" ] && install_skill "./$dir" "$name" "$temp_dir"
  done
fi

rm -rf "$temp_dir"

printf "\n"
print_success
warn "Restart your tool(s) to load skills."
printf "\n"
info "Re-run anytime to update."
printf "\n"
