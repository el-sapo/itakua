---
name: itakua-setup
description: Create, bootstrap, repair, or migrate the machine-local setup of an Itakua brain. Use when creating a brain; bringing a fresh clone or moved checkout into working order; fixing missing, dangling, or unavailable docs/drive attachments; resolving absent or mismatched repository-local Git identity; restoring a README-declared _tmp/ folder; or configuring portable and local artifact mappings.
---

# Set up an Itakua brain

Read the sibling `../itakua-map/SKILL.md` before acting. It defines the structure and
approval boundaries; do not infer or restate them here. This skill owns creation and
machine-local setup only.

## Choose the workflow

- **Create a brain:** resolve this skill's directory, then run its `new-brain.sh` from any
  directory.
- **Repair or initialize a clone:** work through the checkout procedure below.
- **Attach artifacts only:** inspect its maps, then run this skill's `link-drive.sh` from
  the brain root.
- **Create nodes or operate normally:** return to `itakua-map`.

Never write the resolved path of an installed skill or plugin cache into a brain. Refer
to skills and scripts by name in durable files; resolve their installed paths only for the
current command.

## Create a brain

Run:

```sh
<itakua-setup>/scripts/new-brain.sh <path> "<Name>" --identity "Name <email>"
```

Add `--local-only` when the brain must never have a hosted remote, or
`--into-existing` when scaffolding around existing files. The script refuses to overwrite
existing files and does not copy either skill into the new repository.

Afterward, load `itakua-map` to create the first node and validate normal structure.

## Bring a checkout into working order

Run these checks from the brain root:

1. Read the root `README.md`, then the node README for anything you will touch.
2. Locate the sibling map skill and run
   `python3 <itakua-map>/scripts/check-structure.py` using its actual installed directory
   for this command. Do not persist that resolved directory.
3. Compare the README's Git identity binding with repository-local `user.name` and
   `user.email`. Set only `--local` values. If the README does not declare the intended
   identity, ask the owner rather than borrowing the global identity.
4. Restore `_tmp/` only for nodes whose README declares it and where the directory is
   missing. Its contents remain local and its declared contract still applies.
5. If an indexed artifact layer is absent or dangling, inspect `drive-map` and
   `.drive-map.local`, make the cloud folders available offline, and run the linker.
6. Run the map validator again. Report unresolved mappings or unavailable storage as
   explicit setup gaps; do not invent targets.

## Attach artifacts

`drive-map` is committed knowledge: each line maps a node path relative to `spaces/` to a
path relative to this machine's artifact root. `.drive-map.local` is gitignored and holds
absolute overrides for genuine machine exceptions. Local entries win.

```text
# drive-map
guitar|Guitarra

# .drive-map.local
shared-project|/absolute/path/outside/the/common/root
```

Run from the brain root:

```sh
<itakua-setup>/scripts/link-drive.sh "/absolute/path/to/artifact-root"
```

Use `--convention` only for a deliberate greenfield layout that mirrors node paths. The
linker otherwise requires an explicit portable or local mapping for an indexed node. It
does not need a separate marker for local-only targets: an entry in `.drive-map.local` is
the machine-local declaration, and another clone will surface that node as unmapped until
an agent or owner supplies its local value.

The linker refuses relative or unavailable roots and does not replace an existing link or
file. If the local cloud mirror is invisible to the agent, give the exact terminal command
to the owner instead of approximating the path.

## Script ownership

| Skill | Scripts |
|---|---|
| `itakua-setup` | `new-brain.sh`, `link-drive.sh`, and mapping examples |
| `itakua-map` | `new-node.sh`, `check-structure.py`, `index-artifacts.py`, and the node template |

Resolve a script within its owning skill at execution time. Do not duplicate scripts
between skills.
