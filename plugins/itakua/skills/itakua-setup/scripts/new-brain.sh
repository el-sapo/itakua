#!/usr/bin/env bash
# Scaffold a NEW Itakua brain: a fresh instance of the framework, not a copy of one.
#
#   ./new-brain.sh ~/Documents/mybrain "My Brain"
#
# Run it from anywhere. It creates a plain folder with the spine: README.md with the
# bindings table, AGENTS.md, drive-map, 00-inbox/ and spaces/. Nothing else. A brain
# needs no sync; git, Syncthing, Dropbox or iCloud are add-ons the itakua-sync skill
# puts on afterwards. The framework itself is not copied in: it lives in the installed
# plugin skills, which apply to every brain operated by that account.
#
# --local-only  declares "sync: none, deliberately" in the README and records the
#               two-way boundary, for a brain whose material must not leave this
#               machine. The declaration is what itakua-sync's check reads.
#
# --into-existing
#               Scaffold into a folder that already has something in it. Existing
#               files are NEVER overwritten; each one is reported as kept.
#
# A skill is installed per agent ACCOUNT, not per machine. Standing a brain up on a
# second account means installing the skill there first; nothing on disk does it.

set -euo pipefail

LOCAL_ONLY=""; INTO_EXISTING=""; POSITIONAL=(); NPOS=0

# Parse flags BEFORE reading positionals, or `new-brain.sh --local-only ~/foo "X"`
# creates a directory literally named "--local-only".
while [ $# -gt 0 ]; do
  case "$1" in
    --local-only)    LOCAL_ONLY=1 ;;
    --into-existing) INTO_EXISTING=1 ;;
    --*) echo "error: unknown flag $1" >&2; exit 1 ;;
    *) POSITIONAL[$NPOS]="$1"; NPOS=$((NPOS + 1)) ;;
  esac
  shift
done

DEST="${POSITIONAL[0]:-}"; NAME="${POSITIONAL[1]:-}"

usage() {
  echo "usage: new-brain.sh <path> <name> [--local-only] [--into-existing]" >&2
}

if [ -z "$DEST" ] || [ -z "$NAME" ]; then usage; exit 1; fi
# Counters rather than ${#arr[@]}: on bash 3.2 (what macOS ships) that trips `set -u`
# when the array is empty, which is exactly the no-arguments case this must report.
if [ "$NPOS" -gt 2 ]; then
  echo "error: unexpected extra argument '${POSITIONAL[2]}'" >&2; usage; exit 1
fi

DEST="${DEST/#\~/$HOME}"
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ] && [ -z "$INTO_EXISTING" ]; then
  echo "error: $DEST exists and is not empty -- refusing to scaffold over it" >&2
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
DEST="$(cd "$DEST" && pwd)"

write_file "$DEST/drive-map" <<'EOF'
# Portable artifact mappings; they travel with the brain.
# Format: <node path>|<path relative to the cloud artifact root>
# Node paths are relative to spaces/.
#
# french|French class
# house/renovation|House/Renovation
EOF

write_file "$DEST/AGENTS.md" <<EOF
# $NAME

This folder is an Itakua brain. Load the \`itakua-map\` skill before reading, writing
or filing anything here. For a copy on a new machine, or a missing \`docs/drive\` link,
load \`itakua-setup\`; for anything about how this brain travels between machines, load
\`itakua-sync\`. \`README.md\` holds this brain's bindings.
EOF

if [ -n "$LOCAL_ONLY" ]; then
  SYNC_DESC="**none, deliberately** -- see above"
else
  SYNC_DESC="none *(a complete setup; load \`itakua-sync\` to add one)*"
fi

TMPR="$(mktemp)"
trap 'rm -f "$TMPR"' EXIT

{
cat <<EOF
# $NAME

A personal knowledge base: distilled knowledge as markdown in this folder, binary
artifacts in cloud storage reached through \`docs/drive\` links, and the operating rules in
the **\`itakua-map\`** skill. **\`itakua-setup\`** stands a copy up on a machine;
**\`itakua-sync\`** owns whatever carries the brain between machines, if anything does.

\`\`\`
$(basename "$DEST")/
├── README.md      <- you are here: bindings, and how to stand it up elsewhere
├── AGENTS.md      <- pointer for agents
├── drive-map      <- node-to-artifact-folder mappings
├── 00-inbox/      <- capture anything, sort later
└── spaces/        <- all content. Each folder is a node with its own README
\`\`\`
EOF

if [ -n "$LOCAL_ONLY" ]; then
cat <<'EOF'

## This brain stays on this machine

It holds material that must not leave it. **No sync is configured, and none should be
added**: no git remote, no Syncthing share, and not a folder that Dropbox, iCloud, Google
Drive or OneDrive carries. Backup, if you need it, is whatever the material's owner
already sanctions, never a personal account. The `itakua-sync` check warns when this
folder sits inside a synced one.

### The boundary, in both directions

- **Nothing personal comes in.** This is work kit; keep it that way.
- **Nothing crosses out automatically.** If you learn something here that is
  genuinely general craft knowledge, do not copy the file. Write it fresh, in your
  own words, in the personal brain -- without names, figures, client identities or
  code. Rewriting is the check that what crosses is actually general.
EOF
fi

cat <<EOF

## This brain's bindings

A brain is an instance of the framework. The framework is **account-agnostic**: it has no
opinion on whose accounts you use. These are this brain's, and they are the first thing to
check when something goes to the wrong place.

| Binding | This brain |
|---|---|
| **Path** | \`$DEST\` |
| **Sync** | $SYNC_DESC |
| **Cloud storage** | *(which account holds \`docs/\` artifacts -- fill in)* |
| **Agent account** | *(which account operates this brain -- fill in)* |

Mark which of these are **constraints** and which are **preferences**. They look identical
here, and a constraint you can relax by accident is not a constraint.

## Setting this up on a new machine

**1. Install the Itakua plugin** into whichever agent you use. It supplies \`itakua-map\`,
\`itakua-setup\` and \`itakua-sync\`; framework code is not copied into this brain.

**A skill installs per agent account, not per machine.** A second account on the same
computer starts with nothing, and this is the step people skip.

**2. Get the brain onto the machine** the way its Sync row says, or copy the folder.

**3. Start a fresh agent session**, then ask it to load \`itakua-setup\` and bring this
copy into working order: it validates the tree and attaches mapped artifacts when their
machine-local cloud root is available. Portable node-to-folder mappings live in
\`drive-map\`; absolute overrides for one machine live in \`.drive-map.local\`, which
never travels.

## Creating the first node

After setup, load \`itakua-map\` and ask the agent to create \`spaces/<node>\`. That skill
owns normal node creation and validation; keep machine-specific installed-skill paths out
of this brain.
EOF
} > "$TMPR"

write_file "$DEST/README.md" < "$TMPR"

echo "$NAME scaffolded at $DEST"
if [ -n "$KEPT" ]; then
  echo "   kept (already present, not overwritten):$KEPT"
fi
echo "   framework: installed plugin skills itakua-map, itakua-setup, itakua-sync (no copy here)"
if [ -n "$LOCAL_ONLY" ]; then
  echo "   sync: none, deliberately -- declared in README.md"
else
  echo "   sync: none. A brain needs none; load itakua-sync to add git, Syncthing, Dropbox or iCloud"
fi
echo "   remember: the skill installs per agent ACCOUNT, not per machine"
echo "   next: create the first node -- see README.md"
