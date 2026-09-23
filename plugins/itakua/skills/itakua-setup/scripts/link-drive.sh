#!/usr/bin/env bash
# Attach each node's docs/drive symlink to its cloud artifact folder.
#
# RUN FROM THE ROOT OF THE BRAIN REPO, from a real terminal on the Mac:
#
#   <itakua-setup>/scripts/link-drive.sh "/absolute/path/to/cloud-root"
#
# Portable mappings live in committed `drive-map` at the brain root:
#
#   guitar|Guitarra
#   projects/demo|CLIENTS/Demo
#
# The right side is relative to the machine-local root supplied on the command line.
# Genuine machine exceptions live in gitignored `.drive-map.local` as absolute targets:
#
#   projects/demo|/absolute/path/on/this/machine/Demo
#
# Local overrides win over portable mappings. An indexed node missing from both maps is
# reported as unmapped so an agent or owner can resolve the gap; the script does not guess.
# For a deliberately greenfield layout, opt into <ROOT>/<node path> creation explicitly:
#
#   <itakua-setup>/scripts/link-drive.sh --convention "/absolute/path/to/cloud-root"
#
# Agents working through a hosted bridge may not see local absolute paths. In that case,
# run this script yourself from the machine that owns the cloud mirror.
#
# Bash 3.2 compatible on purpose: macOS still ships /bin/bash 3.2.

set -euo pipefail

usage() {
  echo "usage: link-drive.sh [--convention] [absolute-drive-root]" >&2
}

CONVENTION=""
DRIVE_ROOT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --convention) CONVENTION=1 ;;
    -h|--help) usage; exit 0 ;;
    --*) echo "error: unknown option $1" >&2; usage; exit 1 ;;
    *)
      if [ -n "$DRIVE_ROOT" ]; then
        echo "error: more than one Drive root supplied" >&2; usage; exit 1
      fi
      DRIVE_ROOT="$1"
      ;;
  esac
  shift
done

if [ ! -d spaces ]; then
  echo "error: no spaces/ in $(pwd)" >&2
  echo "       Run this from the root of the brain repo." >&2
  exit 1
fi

if [ -n "$DRIVE_ROOT" ]; then
  case "$DRIVE_ROOT" in
    /*) ;;
    *) echo "error: Drive root must be an absolute path: $DRIVE_ROOT" >&2; exit 1 ;;
  esac
  if [ ! -d "$DRIVE_ROOT" ]; then
    echo "error: Drive root does not exist or is unavailable: $DRIVE_ROOT" >&2
    echo "       Sign in or mount it first; this script will not create the root." >&2
    exit 1
  fi
  DRIVE_ROOT="$(cd "$DRIVE_ROOT" && pwd -P)"
elif [ -n "$CONVENTION" ]; then
  echo "error: --convention requires an absolute Drive root" >&2
  exit 1
fi

PORTABLE_MAP="drive-map"
LOCAL_MAP=".drive-map.local"

lookup() {  # map file, node -> mapped value, or empty
  [ -f "$1" ] || return 0
  awk -F'|' -v n="$2" '
    !/^[[:space:]]*#/ && NF >= 2 && $1 == n { sub(/\r$/, "", $2); print $2; exit }
  ' "$1"
}

portable_path_ok() {
  [ -n "$1" ] || return 1
  case "$1" in /*) return 1 ;; esac
  case "/$1/" in *"/../"*|*"/./"*|*"//"*) return 1 ;; esac
  return 0
}

# Match check-structure.py's boundary: once traversal enters a node slot, everything below
# it remains filing, even if a subfolder happens to contain its own README.md.
is_node_dir() {
  local candidate="$1" rest part current state
  case "$candidate" in spaces/*) ;; *) return 1 ;; esac
  rest="${candidate#spaces/}"
  current="spaces"
  state="container"
  while [ -n "$rest" ]; do
    case "$rest" in
      */*) part="${rest%%/*}"; rest="${rest#*/}" ;;
      *) part="$rest"; rest="" ;;
    esac
    if [ "$state" = "node" ]; then
      case "$part" in notes|log|docs|_tmp) return 1 ;; esac
    elif [ "$state" = "orphan" ]; then
      return 1
    fi
    current="$current/$part"
    if [ -f "$current/README.md" ]; then state="node"; else state="orphan"; fi
  done
  [ "$state" = "node" ]
}

# Find direct docs/ slots belonging to actual nodes.
DOCSDIRS=(); NDOCS=0
while IFS= read -r d; do
  [ -n "$d" ] || continue
  node_dir="${d%/docs}"
  is_node_dir "$node_dir" || continue
  DOCSDIRS[$NDOCS]="$d"
  NDOCS=$((NDOCS + 1))
done < <(find spaces -type d -name docs | sed 's|^\./||' | sort)

if [ "$NDOCS" -eq 0 ]; then
  echo "error: no node docs/ slots under spaces/ — nothing to link." >&2
  exit 1
fi

status=0
for docsdir in "${DOCSDIRS[@]}"; do
  node="${docsdir#spaces/}"; node="${node%/docs}"
  link="$docsdir/drive"
  local_target="$(lookup "$LOCAL_MAP" "$node")"
  portable_target="$(lookup "$PORTABLE_MAP" "$node")"
  target=""; origin=""

  if [ -n "$local_target" ]; then
    case "$local_target" in
      /*) ;;
      *)
        echo "  INVALID  $node — $LOCAL_MAP targets must be absolute: $local_target" >&2
        status=1; continue
        ;;
    esac
    target="$local_target"; origin="local override"
    if [ ! -d "$target" ]; then
      echo "  MISSING  $node -> $target (local override is unavailable)" >&2
      status=1; continue
    fi
  elif [ -n "$portable_target" ]; then
    if ! portable_path_ok "$portable_target"; then
      echo "  INVALID  $node — drive-map target must be a safe relative path: $portable_target" >&2
      status=1; continue
    fi
    if [ -z "$DRIVE_ROOT" ]; then
      echo "  unmapped $node — drive-map needs an absolute Drive root on this machine" >&2
      status=1; continue
    fi
    target="$DRIVE_ROOT/$portable_target"; origin="portable"
    if [ ! -d "$target" ]; then
      echo "  MISSING  $node -> $target (portable mapped folder is unavailable)" >&2
      status=1; continue
    fi
  elif [ -n "$CONVENTION" ]; then
    target="$DRIVE_ROOT/$node"; origin="explicit convention"
    [ -d "$target" ] || mkdir -p "$target"
  elif [ -f "$docsdir/index.md" ]; then
    echo "  unmapped $node — index.md exists but neither drive-map nor $LOCAL_MAP has an entry" >&2
    echo "           inspect the node and cloud folder, then add a portable or local mapping" >&2
    status=1; continue
  else
    echo "  skip     $node — docs/ is unused and has no mapping"
    continue
  fi

  if [ -L "$link" ]; then
    if [ "$(readlink "$link")" = "$target" ]; then
      echo "  ok       $link  [$origin]"
    else
      echo "  SKIP     $link points to $(readlink "$link"), expected $target" >&2
      echo "           remove or relink it only with owner approval" >&2
      status=1
    fi
  elif [ -e "$link" ]; then
    echo "  SKIP     $link exists and is not a symlink" >&2
    status=1
  else
    ln -s "$target" "$link"
    echo "  linked   $link -> $target  [$origin]"
  fi
done

echo
echo "$NDOCS node docs/ slot(s) inspected."
echo "Mark each linked folder 'Available offline' in Drive for Desktop —"
echo "streamed placeholders are unreliable for agents."
exit $status
