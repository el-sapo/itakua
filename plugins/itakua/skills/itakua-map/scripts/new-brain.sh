#!/usr/bin/env bash
# Scaffold a NEW Itakua brain — a fresh instance of this framework, not a clone
# of an existing one.
#
#   ./new-brain.sh ~/Documents/mybrain "My Brain" --identity "You <you@example.com>"
#
# Run it from anywhere; it creates the folder, the spine and a git repo with NO
# remote. The framework itself is not copied in: it lives in the installed skill,
# which applies to every brain operated by that account. One copy, no drift.
#
# --local-only  marks the brain as never-published in its README, and records the
#               two-way boundary. There is no remote to push to, which is the
#               actual control; this documents why, for whoever reads it later.
#
# --with-skill  ALSO copy the skill into skill/, so the brain can be stood up from
#               a clone alone where the skill is not installed. Costs you a second
#               copy of the framework that can drift from the source. Note that it
#               does NOT copy .packaged, so drift detection stays off in the new
#               brain — the generated README says so and gives the command.
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

LOCAL_ONLY=""; WITH_SKILL=""; IDENTITY=""; INTO_EXISTING=""; POSITIONAL=(); NPOS=0

# Parse flags BEFORE reading positionals, or `new-brain.sh --local-only ~/foo "X"`
# creates a directory literally named "--local-only".
while [ $# -gt 0 ]; do
  case "$1" in
    --local-only)    LOCAL_ONLY=1 ;;
    --with-skill)    WITH_SKILL=1 ;;
    --into-existing) INTO_EXISTING=1 ;;
    --identity)      shift; IDENTITY="${1:-}" ;;
    --*) echo "error: unknown flag $1" >&2; exit 1 ;;
    *) POSITIONAL[$NPOS]="$1"; NPOS=$((NPOS + 1)) ;;
  esac
  shift
done

DEST="${POSITIONAL[0]:-}"; NAME="${POSITIONAL[1]:-}"

usage() {
  echo "usage: new-brain.sh <path> <name> [--local-only] [--with-skill]" >&2
  echo "                    [--into-existing] [--identity \"Name <email>\"]" >&2
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

# Where this script lives: the installed skill, or a repo's skill/scripts/.
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for f in SKILL.md scripts/check-structure.py; do
  [ -f "$SRC/$f" ] || { echo "error: cannot find $f next to this script ($SRC)" >&2; exit 1; }
done

KEPT=""
# Write stdin to $1, but never over a file that is already there.
write_file() {
  if [ -e "$1" ]; then cat > /dev/null; KEPT="$KEPT ${1#$DEST/}"; return 0; fi
  cat > "$1"
}

mkdir -p "$DEST"/{00-inbox,spaces}
touch "$DEST/00-inbox/.gitkeep" "$DEST/spaces/.gitkeep"
if [ -n "$WITH_SKILL" ]; then
  mkdir -p "$DEST"/skill/{scripts,assets/template/notes,assets/template/log,assets/template/_tmp}
  cp "$SRC/SKILL.md" "$DEST/skill/"
  cp "$SRC"/scripts/*.py "$SRC"/scripts/*.sh "$SRC"/scripts/*.example "$DEST/skill/scripts/" 2>/dev/null || true
  [ -f "$SRC/assets/template/README.md" ] && cp "$SRC/assets/template/README.md" "$DEST/skill/assets/template/"
  touch "$DEST/skill/assets/template/notes/.gitkeep" \
        "$DEST/skill/assets/template/log/.gitkeep" \
        "$DEST/skill/assets/template/_tmp/.gitkeep"
  chmod +x "$DEST"/skill/scripts/*.sh 2>/dev/null || true
fi

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

# --- Local-only ---
.obsidian/
.trash/
.coda/
_tmp/
.drive-map.local
skill/scripts/*.local
*.skill
EOF

write_file "$DEST/CLAUDE.md" <<EOF
# $NAME

This repository is an Itakua brain. **The framework is not described here** — it
lives in the \`itakua-map\` skill. Load it before reading, writing or filing anything.

See \`README.md\` for how to stand this up on a new machine.
EOF

write_file "$DEST/AGENTS.md" <<EOF
# $NAME

This repository is an Itakua brain. Load the \`itakua-map\` skill before reading,
writing, or filing anything. See \`README.md\` for setup and bindings.
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
storage surfaced through symlinks, and the rules for operating it in the
**\`itakua-map\` skill**${WITH_SKILL:+, a copy of which is in \`skill/\`}.

\`\`\`
$(basename "$DEST")/
├── README.md      ← you are here. How to stand this up from a clone${WITH_SKILL:+
├── skill/         ← the framework, installable. SKILL.md + template + scripts}
├── 00-inbox/      ← capture anything, sort later
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

\`check-structure.py --git\` reads the first three back off the repository and compares them
to this table. Run it after anything that touches git.
EOF

if [ -n "$WITH_SKILL" ]; then
cat <<'EOF'

## Setting this up on a new machine

**1. The framework is in `skill/`**, copied in when this brain was scaffolded. Install
it into whichever agent you use — **a skill installs per agent account, not per machine**,
so every account that operates this brain needs its own install.

> **Drift detection is off in this brain.** `--with-skill` deliberately does not copy
> `skill/.packaged`, because that stamp asserts "packaged *and installed*", which was not
> true at scaffold time. Once you have actually installed this copy, turn it on:
>
> ```sh
> python3 skill/scripts/check-structure.py --stamp
> ```

**2. Verify the structure is intact.**

```sh
python3 skill/scripts/check-structure.py --git
```

**3. Attach artifacts (optional).** If this brain references cloud-synced documents,
mark each folder **Available offline** — a streamed folder does not even enumerate
for an agent — then create the symlinks once per machine:

```sh
skill/scripts/link-drive.sh "<your cloud root>"
```

Per-node targets, including a different cloud account, go in `.drive-map.local`
at the root of this repository (gitignored — it holds real paths).

## Creating the first node

```sh
skill/scripts/new-node.sh spaces/<node>
# with owner approval, edit the README placeholders
python3 skill/scripts/check-structure.py
```
EOF
else
cat <<'EOF'

## Setting this up on a new machine

**1. Install the `itakua-map` skill** into whichever agent you use. Nothing in this
repository explains the structure, and that is deliberate: the framework lives in
one installed copy that serves every brain that account operates.

**A skill installs per agent account, not per machine.** A second account on the same
computer starts with nothing, and this is the step people skip.

**2. Verify the structure is intact.**

```sh
python3 @SKILL@/scripts/check-structure.py --git
```

**3. Attach artifacts (optional).** If this brain references cloud-synced documents,
mark each folder **Available offline** — a streamed folder does not even enumerate
for an agent — then create the symlinks once per machine:

```sh
@SKILL@/scripts/link-drive.sh "<your cloud root>"
```

Per-node targets, including a different cloud account, go in `.drive-map.local`
at the root of this repository (gitignored — it holds real paths).

## Creating the first node

```sh
@SKILL@/scripts/new-node.sh spaces/<node>
# with owner approval, edit the README placeholders
python3 @SKILL@/scripts/check-structure.py
```
EOF
fi
} > "$TMPR"

# Point the README's commands at wherever the framework actually is on this machine.
# Absolute, so the README's commands work from anywhere and are unambiguous.
# Done on the temp copy, then written: `{ ... } | write_file` would run write_file in
# a SUBSHELL, and the list of kept files it records would be discarded with it.
if [ -z "$WITH_SKILL" ]; then
  python3 - "$TMPR" "$SRC" <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); p.write_text(p.read_text().replace("@SKILL@", sys.argv[2]))
PYEOF
fi
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
if [ -n "$WITH_SKILL" ]; then
  echo "   framework: copied into skill/ — drift detection is OFF until you run --stamp"
else
  echo "   framework: the installed itakua-map skill (no copy in this folder)"
fi
if [ -n "$IDENTITY" ]; then
  echo "   git identity: $(git config --local user.name) <$(git config --local user.email)> (local to this repo)"
else
  echo "   ⚠ no --identity given: set one before committing, or git will guess"
  echo "     git -C \"$DEST\" config --local user.email you@example.com"
fi
echo "   remember: the skill installs per agent ACCOUNT, not per machine"
echo "   next: create the first node — see README.md"
