#!/usr/bin/env bash
# Link every node's docs/ folder to its Google Drive counterpart.
#
# RUN FROM THE ROOT OF THE BRAIN REPO, from a real terminal on the Mac:
#
#   ./skill/scripts/link-drive.sh "/path/to/your/cloud-storage/itakua-docs"
#
# It operates on the CURRENT DIRECTORY, not on where this file lives, so the copy
# bundled with the installed skill and the copy in skill/scripts/ behave identically.
# If there is no spaces/ here, it stops — a setup script must never report success
# while doing nothing.
#
# Agents working through a hosted bridge may not see local absolute paths. In that case,
# run this script yourself from the machine that owns the cloud mirror.
#
# Run ONCE PER MACHINE. The symlinks are gitignored and machine-specific (Drive paths
# contain your account address), so they never travel with the repo.
#
# TWO WAYS TO POINT A NODE AT DRIVE
#
#  1. Convention (default). Pass a root; each node maps to <ROOT>/<node path>:
#       spaces/guitar/docs/drive                -> <ROOT>/guitar
#       spaces/projects/demo/docs/drive         -> <ROOT>/projects/demo
#
#  2. Override. Any node listed in .drive-map.local — at the ROOT OF THE BRAIN, beside
#     spaces/ — goes wherever you say:
#     a pre-existing cloud folder, a different sharing scope, or a different account.
#     Each account may mount at a different machine-local path.
#     That file is gitignored because the paths are machine-specific.
#
#     Format — "<node path>|<absolute target>", # for comments. The node path is
#     relative to spaces/:
#       guitar|/path/to/cloud-storage/Guitar
#       projects/demo|/path/to/cloud-storage/Demo

set -euo pipefail

if [ ! -d spaces ]; then
  echo "error: no spaces/ in $(pwd)" >&2
  echo "       Run this from the root of the brain repo." >&2
  exit 1
fi

DRIVE_ROOT="${1:-}"
MAP=".drive-map.local"
# Older brains kept this inside the framework directory, which coupled the tooling to a
# layout that changes. If the old copy is the only one, use it and say so — a silent
# fallback is how this same line broke twice before.
if [ ! -f "$MAP" ] && [ -f "skill/scripts/drive-map.local" ]; then
  MAP="skill/scripts/drive-map.local"
  echo "  note: using the legacy map at $MAP" >&2
  echo "        move it to .drive-map.local at the brain root; the framework may not live here for long" >&2
fi

lookup() {  # node -> overridden target, or empty
  [ -f "$MAP" ] || return 0
  awk -F'|' -v n="$1" '!/^[[:space:]]*#/ && $1==n {print $2; exit}' "$MAP"
}

# NOTE: bash 3.2 compatible on purpose. macOS ships bash 3.2.57 as /bin/bash, and
# `#!/usr/bin/env bash` resolves to it unless Homebrew bash is installed AND ahead on
# PATH. `mapfile` is bash 4.0+, so under `set -euo pipefail` it killed this script on
# its first real statement, on the one platform this script exists for. Do not
# reintroduce it, `declare -A`, or `${var^^}`.
#
# The explicit counter is also deliberate: in bash 3.2, `${#arr[@]}` on an EMPTY array
# trips `set -u`, so the "nothing to link" branch below could never be reached.
DOCSDIRS=(); NDOCS=0
while IFS= read -r d; do
  [ -n "$d" ] || continue
  DOCSDIRS[$NDOCS]="$d"
  NDOCS=$((NDOCS + 1))
done < <(find spaces -type d -name docs | sed 's|^\./||' | sort)

if [ "$NDOCS" -eq 0 ]; then
  echo "error: no docs/ folders under spaces/ — nothing to link." >&2
  echo "       A node gets one when it has artifacts. Create it first." >&2
  exit 1
fi

status=0
# NOT a pipeline: a `while` on the right of a `|` runs in a subshell, so every
# failure it recorded would be discarded and this script would exit 0 regardless.
for docsdir in "${DOCSDIRS[@]}"; do
    node="${docsdir#spaces/}"; node="${node%/docs}"
    link="$docsdir/drive"

    target="$(lookup "$node")"
    if [ -n "$target" ]; then
      origin="override"
    elif [ -n "$DRIVE_ROOT" ]; then
      target="$DRIVE_ROOT/$node"; origin="convention"
    else
      echo "  unmapped $node — not in $MAP and no root given" >&2; status=1; continue
    fi

    if [ ! -d "$target" ]; then
      if [ "$origin" = "override" ]; then
        echo "  MISSING  $node -> $target (override target does not exist)" >&2; status=1; continue
      fi
      mkdir -p "$target"
    fi

    if [ -L "$link" ]; then
      if [ "$(readlink "$link")" = "$target" ]; then echo "  ok       $link  [$origin]"
      else
        echo "  SKIP     $link points to $(readlink "$link"), expected $target" >&2
        echo "           remove or relink it only with owner approval" >&2
        status=1
      fi
    elif [ -e "$link" ]; then
      echo "  SKIP     $link exists and is not a symlink" >&2; status=1
    else
      ln -s "$target" "$link"; echo "  linked   $link -> $target  [$origin]"
    fi
done

echo
echo "$NDOCS docs/ folder(s) processed."
echo "Mark each linked folder 'Available offline' in Drive for Desktop —"
echo "streamed placeholders are unreliable for agents."
exit $status
