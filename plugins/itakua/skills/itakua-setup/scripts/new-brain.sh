#!/usr/bin/env bash
# Scaffold a NEW Itakua brain — a fresh instance of this framework, not a clone
# of an existing one.
#
#   ./new-brain.sh ~/Documents/mybrain "My Brain" --identity "You <you@example.com>"
#
# Run it from anywhere; it creates the folder, the spine and a git repo with NO
# remote. The framework itself is not copied in: it lives in the installed plugin
# skills, which apply to every brain operated by that account. One maintained install.
#
# --local-only  marks the brain as never-published in its README, and records the
#               two-way boundary. There is no remote to push to, which is the
#               actual control; this documents why, for whoever reads it later.
#
# --identity "Name <email>"
#               Set this brain's git identity LOCALLY, so commits here cannot be
#               authored as whoever another brain on this machine belongs to. Each
#               brain binds its own identity; the framework has no opinion on which.
#               Validated: a malformed value is rejected rather than committed.
#
# --into-existing
#               Scaffold into a folder that already has something in it. Existing
#               files are NEVER overwritten — each one is reported as kept. Use it
#               to turn a folder you already have into a brain.
#
# A skill is installed per agent ACCOUNT, not per machine. Standing a brain up on a
# second account means installing the skill there first; nothing on disk does it.

set -euo pipefail

LOCAL_ONLY=""; IDENTITY=""; INTO_EXISTING=""; POSITIONAL=(); NPOS=0

# Parse flags BEFORE reading positionals, or `new-brain.sh --local-only ~/foo "X"`
# creates a directory literally named "--local-only".
while [ $# -gt 0 ]; do
  case "$1" in
    --local-only)    LOCAL_ONLY=1 ;;
    --into-existing) INTO_EXISTING=1 ;;
    --identity)      shift; IDENTITY="${1:-}" ;;
    --*) echo "error: unknown flag $1" >&2; exit 1 ;;
    *) POSITIONAL[$NPOS]="$1"; NPOS=$((NPOS + 1)) ;;
  esac
  shift
done

DEST="${POSITIONAL[0]:-}"; NAME="${POSITIONAL[1]:-}"

usage() {
  echo "usage: new-brain.sh <path> <name> [--local-only] [--into-existing]" >&2
  echo "                    [--identity \"Name <email>\"]" >&2
}

if [ -z "$DEST" ] || [ -z "$NAME" ]; then usage; exit 1; fi
# Counters rather than ${#arr[@]}: on bash 3.2 (what macOS ships) that trips `set -u`
# when the array is empty, which is exactly the no-arguments case this must report.
if [ "$NPOS" -gt 2 ]; then
  echo "error: unexpected extra argument '${POSITIONAL[2]}'" >&2; usage; exit 1
fi

# An identity that does not parse is the single most expensive thing this script
# can get wrong: it is silent, it is written into every commit, and it is only
# visible later in `git log`. Reject it here rather than slicing strings and hoping.
if [ -n "$IDENTITY" ]; then
  if ! printf '%s' "$IDENTITY" \
       | grep -Eq '^[^<>]+ <[^<>[:space:]@]+@[^<>[:space:]@]+\.[^<>[:space:]@]+>$'; then
    echo "error: --identity must be exactly \"Name <email@domain>\"" >&2
    echo "       got: [$IDENTITY]" >&2
    exit 1
  fi
fi

DEST="${DEST/#\~/$HOME}"
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ] && [ -z "$INTO_EXISTING" ]; then
  echo "error: $DEST exists and is not empty — refusing to scaffold over it" >&2
  echo "       to add the spine around what is already there, without overwriting" >&2
  echo "       anything, re-run with --into-existing" >&2
  exit 1
fi

KEPT=""
# Write stdin to $1, but never over a file that is already there.
write_file() {
  if [ -e "$1" ]; then cat > /dev/null; KEPT="$KEPT ${1#$DEST/}"; return 0; fi
  cat > "$1"
}

mkdir -p "$DEST"/{00-inbox,spaces}
touch "$DEST/00-inbox/.gitkeep" "$DEST/spaces/.gitkeep"

write_file "$DEST/.gitignore" <<'EOF'
# --- macOS noise ---
.DS_Store
._*
.Spotlight-V100
.Trashes

# --- Layer 1 artifacts: cloud-synced, never versioned ---
# Everything directly inside any docs/ folder EXCEPT markdown index notes.
**/docs/*
!**/docs/*.md

# --- Raw binaries belong in cloud storage, not in git history (permanent!) ---
*.ogg
*.mp3
*.m4a
*.wav
*.mp4
*.mov
*.pdf
*.png
*.jpg
*.jpeg
*.zip

# Generated exports — the markdown source in git is the truth
*.docx
*.xlsx
*.pptx

# --- Inboxes: text is tracked, every other file stays on this machine ---
# An allowlist, not a denylist: an inbox accepts any file, and the list above misses
# .heic, .webp, .gif, .epub and whatever comes next. Git cannot tell a node's inbox/
# slot from any other folder named inbox, so do not name a node or a filing subfolder
# that. An owner who wants a binary versioned anyway can still `git add -f` it.
**/inbox/**
!**/inbox/**/
!**/inbox/**/*.md
!**/inbox/**/*.txt
!**/inbox/**/*.html
!**/inbox/**/.gitkeep
/00-inbox/**
!/00-inbox/**/
!/00-inbox/**/*.md
!/00-inbox/**/*.txt
!/00-inbox/**/*.html
!/00-inbox/**/.gitkeep

# --- Local-only ---
.obsidian/
.trash/
.coda/
.drive-map.local
*.skill
# generated per machine by check-structure.py --report; never committed
/status.html
EOF

write_file "$DEST/drive-map" <<'EOF'
# Portable artifact mappings, committed with the brain.
# Format: <node path>|<path relative to the cloud artifact root>
# Node paths are relative to spaces/.
#
# french|French class
# house/renovation|House/Renovation
EOF

write_file "$DEST/CLAUDE.md" <<EOF
# $NAME

This repository is an Itakua brain. **The framework is not described here** — it
lives in the \`itakua-map\` skill. Load it before reading, writing or filing anything.

For a fresh clone or another setup/repair symptom, load \`itakua-setup\`. See
\`README.md\` for this brain's bindings.
EOF

write_file "$DEST/AGENTS.md" <<EOF
# $NAME

This repository is an Itakua brain. Load the \`itakua-map\` skill before reading,
writing, or filing anything. For a fresh clone or another setup/repair symptom,
load \`itakua-setup\`. See \`README.md\` for bindings.
EOF

if [ -n "$LOCAL_ONLY" ]; then
  REMOTE_DESC="**none, deliberately** — see above"
else
  REMOTE_DESC="*(none yet)*"
fi

TMPR="$(mktemp)"
trap 'rm -f "$TMPR"' EXIT

{
cat <<EOF
# $NAME

A personal knowledge base: distilled knowledge in git as markdown, binary artifacts in cloud
storage surfaced through symlinks, normal operating rules in **\`itakua-map\`**, and
per-machine setup procedures in **\`itakua-setup\`**.

\`\`\`
$(basename "$DEST")/
├── README.md      ← you are here. Bindings and clone setup
├── drive-map      ← portable node-to-artifact-folder mappings
├── 00-inbox/      ← capture anything, sort later (text tracked, the rest local)
└── spaces/         ← all content. Each folder is a node with its own README
\`\`\`
EOF

if [ -n "$LOCAL_ONLY" ]; then
cat <<'EOF'

## ⛔ This brain is local-only

It holds material that must not reach a hosted remote.

**There is no remote configured, and none should be added.** That is the whole
control: `git push` has nowhere to go and fails. Git is here for history, diffs and
recovery — all of which are local — and for nothing else. Backup, if you need it, is
whatever your employer already sanctions, never a personal account.

### The boundary, in both directions

- **Nothing personal comes in.** This is work kit; keep it that way.
- **Nothing crosses out automatically.** If you learn something here that is
  genuinely general craft knowledge, do not copy the file. Write it fresh, in your
  own words, in the personal brain — without names, figures, client identities or
  code. Rewriting is the check that what crosses is actually general.
EOF
fi

cat <<EOF

## This brain's bindings

A brain is an instance of the framework. The framework is **account-agnostic** — it has no
opinion on whose accounts you use. These are this brain's, and they are the first thing to
check when something goes to the wrong place.

| Binding | This brain |
|---|---|
| **Path** | \`$DEST\` |
| **Git remote** | $REMOTE_DESC |
| **Git identity** | ${IDENTITY:-⚠ *not set — do this before committing*} |
| **Cloud storage** | *(which account holds \`docs/\` artifacts — fill in)* |
| **Agent account** | *(which account operates this brain — fill in)* |

Mark which of these are **constraints** and which are **preferences**. They look identical
here, and a constraint you can relax by accident is not a constraint.

The validator in \`itakua-map\` compares the declared Git remote and identity with the
repository. Run it after anything that touches git.
EOF

cat <<'EOF'

## Setting this up on a new machine

**1. Install the Itakua plugin** into whichever agent you use. It supplies both
`itakua-map` and `itakua-setup`; framework code is not copied into this brain.

**A skill installs per agent account, not per machine.** A second account on the same
computer starts with nothing, and this is the step people skip.

**2. Start a fresh agent session**, then ask it to load `itakua-setup` and bring this
clone into working order. The setup skill checks repository-local Git identity, validates
the tree, and attaches mapped artifacts when their machine-local cloud root is available.

Portable node-to-folder mappings live in committed `drive-map`. Machine-specific absolute
overrides live in gitignored `.drive-map.local`.

## Creating the first node

After setup, load `itakua-map` and ask the agent to create `spaces/<node>`. That skill owns
normal node creation and validation; keep machine-specific installed-skill paths out of
this repository.
EOF
} > "$TMPR"

write_file "$DEST/README.md" < "$TMPR"

cd "$DEST"
NEW_REPO=1
[ -d .git ] && NEW_REPO=""
[ -n "$NEW_REPO" ] && git init -q .

# Bind this brain's identity locally. Never fall back to a global or another repo's
# identity: on a machine with more than one brain that is how work commits end up
# authored as a personal account.
if [ -n "$IDENTITY" ]; then
  ID_NAME="${IDENTITY%% <*}"
  ID_MAIL="${IDENTITY##*<}"; ID_MAIL="${ID_MAIL%>}"
  git config --local user.name  "$ID_NAME"
  git config --local user.email "$ID_MAIL"
fi

git add -A
if git diff --cached --quiet; then
  echo "nothing to commit — everything was already present and tracked"
elif [ -n "$IDENTITY" ]; then
  git commit -qm "Scaffold $NAME from the Itakua framework"
else
  git -c user.email="brain@localhost" -c user.name="brain" \
      commit -qm "Scaffold $NAME from the Itakua framework"
fi

echo "✅ $NAME scaffolded at $DEST"
if [ -n "$KEPT" ]; then
  echo "   kept (already present, not overwritten):$KEPT"
fi
[ -n "$LOCAL_ONLY" ] && echo "   local-only: no remote configured, and none should be added"
echo "   framework: installed plugin skills itakua-map + itakua-setup (no copy here)"
if [ -n "$IDENTITY" ]; then
  echo "   git identity: $(git config --local user.name) <$(git config --local user.email)> (local to this repo)"
else
  echo "   ⚠ no --identity given: set one before committing, or git will guess"
  echo "     git -C \"$DEST\" config --local user.email you@example.com"
fi
echo "   remember: the skill installs per agent ACCOUNT, not per machine"
echo "   next: create the first node — see README.md"
