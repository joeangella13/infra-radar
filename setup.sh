#!/usr/bin/env bash
# Infra Radar — one-shot setup.
#
#   ./setup.sh [repo-name]
#
# Creates the GitHub repo, pushes the archive, sets the secrets and variables,
# turns on Pages, and kicks off the first run. Default repo name: infra-radar.

set -euo pipefail

REPO="${1:-infra-radar}"
BOLD=$'\033[1m'; DIM=$'\033[2m'; GRN=$'\033[32m'; YEL=$'\033[33m'; RST=$'\033[0m'
say(){ printf "%s\n" "${BOLD}$*${RST}"; }
note(){ printf "%s\n" "${DIM}$*${RST}"; }
ok(){ printf "%s\n" "${GRN}✓${RST} $*"; }
warn(){ printf "%s\n" "${YEL}!${RST} $*"; }

cd "$(dirname "$0")"

# ---------------------------------------------------------------- preflight
if ! command -v gh >/dev/null 2>&1; then
  cat <<EOF
${BOLD}The GitHub CLI isn't installed.${RST}

  macOS:  brew install gh
  then:   gh auth login

Or follow the manual path in README.md — same result, a few more clicks.
EOF
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  say "Logging you into GitHub first…"
  gh auth login
fi

OWNER="$(gh api user --jq .login)"
ok "Authenticated as ${OWNER}"

# ---------------------------------------------------------------- inputs
say ""
say "Anthropic API key"
note "From https://console.anthropic.com — this is what pays for the daily run."
read -rsp "  ANTHROPIC_API_KEY: " ANTHROPIC_KEY; echo
[ -n "$ANTHROPIC_KEY" ] || { warn "An API key is required."; exit 1; }

say ""
say "Morning email (optional — press Enter twice to skip)"
note "Gmail app password, not your login password:"
note "Google Account → Security → 2-Step Verification → App passwords"
read -rp  "  Gmail address: " MAIL_USER
if [ -n "$MAIL_USER" ]; then
  read -rsp "  App password:  " MAIL_PASS; echo
  read -rp  "  Send digest to [${MAIL_USER}]: " EMAIL_TO
  EMAIL_TO="${EMAIL_TO:-$MAIL_USER}"
fi

# ---------------------------------------------------------------- repo
say ""
say "Creating ${OWNER}/${REPO}…"

if [ ! -d .git ]; then
  git init -q -b main
  git add -A
  git -c user.name="${OWNER}" commit -qm "Infra Radar: initial archive and pipeline"
fi

if gh repo view "${OWNER}/${REPO}" >/dev/null 2>&1; then
  warn "Repo already exists — pushing to it."
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/${OWNER}/${REPO}.git"
  git push -u origin main
else
  gh repo create "${REPO}" --public --source=. --remote=origin --push
fi
ok "Pushed"

SITE_URL="https://${OWNER}.github.io/${REPO}"

# ---------------------------------------------------------------- config
say ""
say "Setting secrets and variables…"
printf '%s' "$ANTHROPIC_KEY" | gh secret set ANTHROPIC_API_KEY --repo "${OWNER}/${REPO}"
ok "ANTHROPIC_API_KEY"

if [ -n "${MAIL_USER:-}" ]; then
  printf '%s' "$MAIL_USER" | gh secret set MAIL_USERNAME --repo "${OWNER}/${REPO}"
  printf '%s' "$MAIL_PASS" | gh secret set MAIL_PASSWORD --repo "${OWNER}/${REPO}"
  gh variable set EMAIL_TO --repo "${OWNER}/${REPO}" --body "$EMAIL_TO"
  ok "Email configured → ${EMAIL_TO}"
else
  note "  Email skipped — the workflow detects this and stays quiet."
fi

gh variable set SITE_URL --repo "${OWNER}/${REPO}" --body "$SITE_URL"
ok "SITE_URL"

# ---------------------------------------------------------------- pages
say ""
say "Turning on GitHub Pages…"
if printf '%s' '{"source":{"branch":"main","path":"/"}}' \
     | gh api -X POST "repos/${OWNER}/${REPO}/pages" --input - >/dev/null 2>&1; then
  ok "Pages enabled"
else
  gh api "repos/${OWNER}/${REPO}/pages" >/dev/null 2>&1 \
    && ok "Pages already enabled" \
    || warn "Enable manually: Settings → Pages → Deploy from a branch → main / (root)"
fi

# ---------------------------------------------------------------- first run
say ""
read -rp "Run the first brief now? [Y/n] " RUNNOW
if [[ ! "${RUNNOW:-Y}" =~ ^[Nn] ]]; then
  gh workflow run daily.yml --repo "${OWNER}/${REPO}" -f lookback_days=2
  ok "Triggered — watch it with:  gh run watch --repo ${OWNER}/${REPO}"
fi

cat <<EOF

${GRN}${BOLD}Done.${RST}

  Site      ${SITE_URL}/
  Repo      https://github.com/${OWNER}/${REPO}
  Actions   https://github.com/${OWNER}/${REPO}/actions

Pages takes a minute or two to publish the first time. After that the cron runs
every weekday at 6:30am ET and the site updates itself.

Tune the watchlists in config.json; tune the writing in scripts/generate.py.
EOF
