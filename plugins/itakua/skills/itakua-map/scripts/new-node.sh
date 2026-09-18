#!/usr/bin/env bash
# Safely scaffold one Itakua node. Run from the root of an Itakua brain.

set -euo pipefail

DEST="${1:-}"

if [ -z "$DEST" ] || [ "$#" -ne 1 ]; then
  echo "usage: new-node.sh spaces/<node>" >&2
  exit 1
fi

case "$DEST" in
  spaces/*) ;;
  *)
    echo "error: node path must be relative to spaces/ (got: $DEST)" >&2
    exit 1
    ;;
esac

case "/$DEST/" in
  *"/../"*|*"/./"*|*"//"*)
    echo "error: node path must not contain '.', '..', or empty segments" >&2
    exit 1
    ;;
esac

if [ ! -d spaces ]; then
  echo "error: no spaces/ in $(pwd) — run from the root of an Itakua brain" >&2
  exit 1
fi

if [ -e "$DEST" ]; then
  echo "error: $DEST already exists — refusing to overwrite it" >&2
  exit 1
fi

PARENT="${DEST%/*}"
if [ "$PARENT" != "spaces" ] && [ ! -f "$PARENT/README.md" ]; then
  echo "error: parent $PARENT is not a node (README.md is missing)" >&2
  exit 1
fi

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$SKILL_ROOT/assets/template"
if [ ! -f "$TEMPLATE/README.md" ]; then
  echo "error: template README not found at $TEMPLATE/README.md" >&2
  exit 1
fi

mkdir -p "$DEST"/{notes,log,_tmp}
cp "$TEMPLATE/README.md" "$DEST/README.md"
touch "$DEST/notes/.gitkeep" "$DEST/log/.gitkeep" "$DEST/_tmp/.gitkeep"

echo "created $DEST with notes/, log/, and manual _tmp/ staging"
echo "next: with owner approval, fill every <placeholder> in $DEST/README.md"
echo "then: run check-structure.py from the brain root"
