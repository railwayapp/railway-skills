#!/usr/bin/env bash
set -e

REPO="https://github.com/railwayapp/railway"

# Colors
BOLD="$(tput bold 2>/dev/null || printf '')"
GREY="$(tput setaf 8 2>/dev/null || printf '')"
RED="$(tput setaf 1 2>/dev/null || printf '')"
GREEN="$(tput setaf 2 2>/dev/null || printf '')"
YELLOW="$(tput setaf 3 2>/dev/null || printf '')"
MAGENTA="$(tput setaf 5 2>/dev/null || printf '')"
CYAN="$(tput setaf 6 2>/dev/null || printf '')"
NO_COLOR="$(tput sgr0 2>/dev/null || printf '')"

info() {
  printf '%s\n' "${BOLD}${GREY}>${NO_COLOR} $*"
}

warn() {
  printf '%s\n' "${YELLOW}! $*${NO_COLOR}"
}

error() {
  printf '%s\n' "${RED}x $*${NO_COLOR}" >&2
}

completed() {
  printf '%s\n' "${GREEN}✓${NO_COLOR} $*"
}

print_header() {
  printf "${MAGENTA}"
  cat <<'EOF'
    ____        _ __                      _____ __   _ ____
   / __ \____ _(_) /      ______ ___  __ / ___// /__(_) / /____
  / /_/ / __ `/ / / | /| / / __ `/ / / / \__ \/ //_/ / / / ___/
 / _, _/ /_/ / / /| |/ |/ / /_/ / /_/ / ___/ / ,< / / / (__  )
/_/ |_|\__,_/_/_/ |__/|__/\__,_/\__, / /____/_/|_/_/_/_/____/
                               /____/
EOF
  printf "${NO_COLOR}\n"
}

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
  printf "${NO_COLOR}"
}

install_skills() {
  local skills_dir="$1"
  local temp_dir=$(mktemp -d)

  info "Downloading from ${CYAN}$REPO${NO_COLOR}..."
  git clone --depth 1 --quiet "$REPO" "$temp_dir"

  mkdir -p "$skills_dir"
  rm -rf "$skills_dir"/railway-* 2>/dev/null || true

  local count=0
  for d in "$temp_dir"/plugins/railway/skills/*/; do
    skill_name=$(basename "$d")
    # Skip _shared and any underscore-prefixed directories
    [[ "$skill_name" == _* ]] && continue
    # Only copy if it contains a SKILL.md
    [ -f "$d/SKILL.md" ] || continue
    cp -R "$d" "$skills_dir/railway-$skill_name"
    count=$((count + 1))
  done

  rm -rf "$temp_dir"

  printf "\n"
  completed "Installed ${GREEN}$count${NO_COLOR} skills to ${CYAN}$skills_dir${NO_COLOR}"
  printf "\n"
  ls -1 "$skills_dir" | grep "^railway-" | sed "s/^/  ${GREY}•${NO_COLOR} /"
}

print_header

printf "  Select your agent:\n\n"
printf "    ${BOLD}1)${NO_COLOR} Claude Code\n"
printf "    ${BOLD}2)${NO_COLOR} OpenAI Codex\n"
printf "    ${BOLD}3)${NO_COLOR} OpenCode\n"
printf "    ${BOLD}4)${NO_COLOR} Cursor\n"
printf "\n"
printf "${MAGENTA}?${NO_COLOR} Choice ${BOLD}[1-4]${NO_COLOR}: "
read -r choice </dev/tty

case $choice in
  1)
    printf "\n"
    printf "  Claude Code install method:\n\n"
    printf "    ${BOLD}1)${NO_COLOR} Plugin ${GREEN}(recommended)${NO_COLOR}\n"
    printf "    ${BOLD}2)${NO_COLOR} Local skills copy\n"
    printf "\n"
    printf "${MAGENTA}?${NO_COLOR} Choice ${BOLD}[1-2]${NO_COLOR}: "
    read -r claude_choice </dev/tty

    case $claude_choice in
      1)
        printf "\n"
        if command -v claude &>/dev/null; then
          info "Adding marketplace source..."
          claude plugin marketplace add railwayapp/railway
          info "Installing plugin..."
          claude plugin install railway@railway
          printf "\n"
          print_success
          warn "Restart Claude Code to load the plugin."
        else
          error "Claude CLI not found."
          printf "\n"
          info "Install manually:"
          printf "  ${CYAN}claude plugin marketplace add railwayapp/railway${NO_COLOR}\n"
          printf "  ${CYAN}claude plugin install railway@railway${NO_COLOR}\n"
        fi
        ;;
      2)
        printf "\n"
        install_skills "$HOME/.claude/skills"
        printf "\n"
        print_success
        warn "Restart Claude Code to load skills."
        ;;
      *)
        error "Invalid choice"
        exit 1
        ;;
    esac
    ;;
  2)
    printf "\n"
    install_skills "$HOME/.codex/skills"
    printf "\n"
    print_success
    warn "Restart Codex to load skills."
    ;;
  3)
    printf "\n"
    install_skills "$HOME/.config/opencode/skill"
    printf "\n"
    print_success
    warn "Restart OpenCode to load skills."
    ;;
  4)
    printf "\n"
    install_skills "$HOME/.cursor/skills"
    printf "\n"
    print_success
    warn "Restart Cursor to load skills."
    ;;
  *)
    error "Invalid choice"
    exit 1
    ;;
esac

printf "\n"
info "Re-run this script anytime to update."
printf "\n"
