---
name: itakua-setup
description: Create, bootstrap, repair, or migrate the machine-local setup of an Itakua brain. Use when creating or cloning a brain; bringing a fresh or moved checkout into working order; diagnosing Git authentication, sandbox permission, or repository configuration failures; fixing missing, dangling, or unavailable docs/drive attachments; resolving absent or mismatched repository-local Git identity; or configuring portable and local artifact mappings.
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
4. If an indexed artifact layer is absent or dangling, inspect `drive-map` and
   `.drive-map.local`, make the cloud folders available offline, and run the linker.
5. Run the map validator again. Report unresolved mappings or unavailable storage as
   explicit setup gaps; do not invent targets.

## Diagnose clone and Git failures

Keep host access separate from repository configuration. A hosted or sandboxed agent may
see the filesystem without sharing the host's keychain, SSH keys, GitHub CLI session, or
interactive credential prompt.

| Signal | Category | Response |
|---|---|---|
| `Authentication failed`, `Permission denied (publickey)`, or an unavailable credential prompt | Host authentication | Stop retrying. Show the failed command and have the owner clone or log in from a local interactive terminal. Give an exact command only when the remote, provider, and authentication method are known; otherwise state what is missing instead of guessing. Never ask them to paste a token or key into chat. |
| `Operation not permitted` or `Permission denied` while creating, renaming, or removing a path under `.git/` | Sandbox/filesystem permission | Report the exact path and failed operation. Agent-driven Git needs create, write, rename, and delete access within this repository's worktree and `.git/`; read/write access without delete is insufficient. |
| `not a git repository`, a wrong remote, or an absent/mismatched local identity | Repository configuration | Inspect `git status`, `git remote -v`, and repository-local config. Repair only the declared repository bindings; do not treat configuration as an authentication failure. |

For `.git/index.lock`, first check whether the file exists and whether a Git process is
using it. Remove only that exact, confirmed stale lock when permitted; otherwise ask the
owner to remove it in the host terminal. If no lock exists and creation itself is blocked,
deletion cannot help: obtain create, write, rename, and delete access scoped to this
worktree and `.git/`, or leave Git mutations to the owner. Never recursively change
`.git/` permissions or delete other lock files speculatively. A checkout created by the
owner does not give the agent remote credentials; later fetch or push operations may need
the same host-side handoff.

Keep these diagnostics out of `check-structure.py`. The structural validator may report
repository state, but it cannot prove that a particular bridge has credentials, an
interactive terminal, or sufficient sandbox permissions.

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

A linked node also declares its Drive folder in the README `artifacts:` key that
`itakua-map` defines, for readers that cannot follow the symlink: its `root`, and
optionally its `url`, the folder's link. After linking, run the map validator: it proposes
the `root` from this machine's mapping, and the `url` where this machine can read the
folder's Drive id; otherwise the link comes from Drive's *Copy link* on the folder.
Writing the key is a README edit and needs owner approval.

## Script ownership

| Skill | Scripts |
|---|---|
| `itakua-setup` | `new-brain.sh`, `link-drive.sh`, and mapping examples |
| `itakua-map` | `new-node.sh`, `check-structure.py`, `index-artifacts.py`, and the node template |

Resolve a script within its owning skill at execution time. Do not duplicate scripts
between skills.
