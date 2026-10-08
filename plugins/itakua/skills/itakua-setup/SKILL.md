---
name: itakua-setup
description: Create an Itakua brain, or bring a copy of one into working order on a machine. Use when creating a brain; when a brain has just been copied, cloned or moved; when a docs/drive attachment is missing, dangling or unavailable; or when configuring the portable and machine-local artifact mappings. Sync tools and their failures belong to itakua-sync.
---

# Set up an Itakua brain

Read the sibling `../itakua-map/SKILL.md` before acting. It defines the structure and
approval boundaries; do not infer or restate them here. This skill owns creation and
machine-local setup only. How a brain travels between machines, if it does, is
`itakua-sync`'s.

## Choose the workflow

- **Create a brain:** resolve this skill's directory, then run its `new-brain.sh` from any
  directory.
- **Bring a copy into working order:** work through the procedure below.
- **Attach artifacts only:** inspect its maps, then run this skill's `link-drive.sh` from
  the brain root.
- **Add or check a sync:** load `itakua-sync`.
- **Create nodes or operate normally:** return to `itakua-map`.

Never write the resolved path of an installed skill or plugin cache into a brain. Refer
to skills and scripts by name in durable files; resolve their installed paths only for the
current command.

## Create a brain

```sh
<itakua-setup>/scripts/new-brain.sh <path> "<Name>"
```

This makes a plain folder with the spine: `README.md` with the bindings table,
`AGENTS.md`, `drive-map`, `00-inbox/` and `spaces/`. No sync is a complete setup; add one
afterwards with `itakua-sync` if the owner wants it. Add `--local-only` for a brain whose
material must never leave the machine: the README then declares *sync: none,
deliberately*, which `itakua-sync`'s check reads. Add `--into-existing` to scaffold
around files already there. The script never overwrites an existing file and does not
copy any skill into the brain.

Afterwards, load `itakua-map` to create the first node and validate the structure.

## Bring a copy into working order

From the brain root:

1. Read the root `README.md`, then the node README for anything you will touch.
2. Locate the sibling map skill and run
   `python3 <itakua-map>/scripts/check-structure.py` using its actual installed directory
   for this command. Do not persist that resolved directory.
3. If an indexed artifact layer is absent or dangling, inspect `drive-map` and
   `.drive-map.local`, make the cloud folders available offline, and run the linker.
4. Run the validator again. Report unresolved mappings or unavailable storage as explicit
   setup gaps; do not invent targets.
5. If the README's Sync row names a tool, load `itakua-sync` and run its check too.

## Attach artifacts

`drive-map` travels with the brain: each line maps a node path relative to `spaces/` to a
path relative to this machine's artifact root. `.drive-map.local` stays on this machine
and holds absolute overrides for genuine machine exceptions. Local entries win.

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
linker otherwise requires an explicit portable or local mapping for an indexed node. An
entry in `.drive-map.local` is the machine-local declaration; another copy of the brain
will surface that node as unmapped until an agent or owner supplies its local value.

The linker refuses relative or unavailable roots and does not replace an existing link or
file. If the local cloud mirror is invisible to the agent, give the exact terminal command
to the owner instead of approximating the path.

A linked node also declares its Drive folder in the README `artifacts:` key that
`itakua-map` defines, for readers that cannot follow the link: its `root`, and optionally
its `url`. After linking, run the map validator: it proposes the `root` from this
machine's mapping, and the `url` where this machine can read the folder's Drive id;
otherwise the link comes from Drive's *Copy link* on the folder. Writing the key is a
README edit and needs owner approval.

## Script ownership

| Skill | Scripts |
|---|---|
| `itakua-setup` | `new-brain.sh`, `link-drive.sh`, and mapping examples |
| `itakua-map` | `new-node.sh`, `check-structure.py`, `index-artifacts.py`, and the node template |
| `itakua-sync` | `check-sync.py` |

Resolve a script within its owning skill at execution time. Do not duplicate scripts
between skills.
