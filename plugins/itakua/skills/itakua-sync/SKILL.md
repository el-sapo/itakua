---
name: itakua-sync
description: Add, check or repair how an Itakua brain travels between machines, with git, Syncthing, Dropbox, iCloud, or none, deliberately. Use when declaring or changing a brain's sync, writing a sync tool's ignore rules, committing or staging in a brain, diagnosing git authentication, sandbox permission, remote or identity failures, finding conflict copies, or checking that a brain declared as never synced sits outside any synced folder.
---

# Sync an Itakua brain

A brain is a folder of plain files and is complete with no sync at all. Everything here
is an add-on. Which files a sync may carry is decided once, in `itakua-map` under **What
travels**: the brain, this machine only, and Drive. Read that table first; this skill only
says how to tell each tool, and what each one gets wrong.

**The one hard rule: no sync carries `docs/drive`.** It is a link into the Drive mirror,
and a tool that follows it copies the whole Drive folder into every machine and every
version. Exclude it before the first sync runs, and verify the exclusion before trusting
it.

## Declare it

The root README's bindings table has a **Sync** row. It says `none`, `none, deliberately`,
or the tool(s) that carry the brain. A brain carried by git also declares **Git remote**
and **Git identity** rows, so the check can compare them with the repository. Changing a
row is a README edit: owner approval.

## One row per tool

| Tool | Exclude a path | Verify | Trap |
|---|---|---|---|
| git | `.gitignore` (the block below) | `git check-ignore -v <path>` | binaries in history are permanent |
| Syncthing | `.stignore` at the folder root | the folder's ignore patterns in the web UI, or `GET /rest/db/ignores?folder=<id>` | the first matching pattern wins, the opposite of git, so order matters; `.stignore` itself is never synced, so write it on every machine |
| Dropbox | per-path attribute, no ignore file: `xattr -w com.dropbox.ignored 1 <path>` on macOS, `attrib +s` on Windows, `attr -s com.dropbox.ignored -V 1` on Linux | `xattr -p com.dropbox.ignored <path>` | the attribute is per machine and lost by a move or copy; set it again after relinking |
| iCloud | only a name ending in `.nosync` | nothing to read; watch what appears on a second device | `docs/drive` cannot be renamed, so nothing excludes it. How iCloud treats the link is untested; until it is, treat iCloud as a mirror with one writer, and confirm on a second device what arrived before relying on it |

Write each tool's rules from the three classes: exclude everything in *this machine only*
(`docs/drive`, `.drive-map.local`, `status.html`), carry everything in *the brain*, and
never touch what `docs/drive` points to. Inbox binaries are the one judgement call, below.

**Inbox binaries travel with any sync except git.** A photo dropped on the phone and
distilled on the Mac is the point of Syncthing or Dropbox. Git keeps them out, because
history is permanent and no denylist keeps up with `.heic`, `.webp` and whatever comes
next; the allowlist below tracks text only. Either way, the rule that holds everywhere is
the map's: binaries end in `docs/`.

**Conflict copies.** Every file sync makes one when two machines edit the same file:
Syncthing `*.sync-conflict-*`, Dropbox `(conflicted copy)`, iCloud `name 2.md`. Captures
never edit a file, so they cannot conflict; only `notes/` and READMEs edited on two
devices can. With one writer there are none: a brain one machine edits and the others
only read or capture into cannot conflict, and the Sync row can say so (`icloud, one
writer: the Mac`). The check lists every copy it finds. Resolving one is an edit to
`notes/` or a README, so it needs owner approval; never delete a copy unread.

A mirror is not a backup. Every tool here propagates a deletion or a bad rewrite within
seconds, and only git keeps every version. The map's answer holds for the layer that
matters, logs are the history, but a brain carried by a file sync alone has no way back
for a deleted note beyond what the tool's trash keeps.

## none, deliberately

A brain whose README says `none, deliberately` holds material that must not leave the
machine: typically a work brain. The declaration is the control, so the check treats any
sync it finds on such a brain as a problem: a git remote, a Syncthing folder marker, or
the brain sitting inside a folder that iCloud Drive, Dropbox, Google Drive or OneDrive
carries. Move the brain out, or get the owner's explicit decision; never quietly change
the declaration to match.

## Git

Git is the one sync with permanent history, so it gets rules of its own.

- **Set up:** `git init`, then a repository-local identity, never the global one:
  `git config --local user.name` and `user.email`. On a machine with more than one brain,
  the global identity is how work commits end up authored as a personal account. Declare
  the identity and the remote (or `none`) in the bindings table.
- **`.gitignore`:** this block. Everything in a `docs/` folder but markdown, every inbox
  file but text, and the machine-local edges. An allowlist for inboxes, because an inbox
  accepts any file.

  ```gitignore
  # Itakua: binaries live in Drive, never in history
  **/docs/*
  !**/docs/*.md

  # Inboxes: text travels, every other file stays on this machine
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

  # This machine only
  .drive-map.local
  /status.html
  .DS_Store
  ```

- **Stage by path, never `git add -A`.** Limbo, and anything else the owner has not
  decided to commit, stays out of the index unless they say so.
- **Never commit a binary.** One in an inbox stays on this machine until it moves to
  `docs/drive`; tell the owner it exists only here. `git add -f` remains an owner override,
  and it is one of the cases that get a second ask (see `itakua-map`, **When the user
  overrides a rule**): history is permanent.
- Do not name a node or a filing subfolder `inbox`: git cannot tell it from the slot, and
  the allowlist would leave anything but text in it untracked.

### Diagnose clone and git failures

Keep host access separate from repository configuration. A hosted or sandboxed agent may
see the filesystem without sharing the host's keychain, SSH keys, GitHub CLI session, or
interactive credential prompt.

| Signal | Category | Response |
|---|---|---|
| `Authentication failed`, `Permission denied (publickey)`, or an unavailable credential prompt | Host authentication | Stop retrying. Show the failed command and have the owner clone or log in from a local interactive terminal. Give an exact command only when the remote, provider, and authentication method are known; otherwise say what is missing. Never ask them to paste a token or key into chat |
| `Operation not permitted` or `Permission denied` while creating, renaming, or removing a path under `.git/` | Sandbox or filesystem permission | Report the exact path and failed operation. Agent-driven git needs create, write, rename, and delete access within this worktree and `.git/`; read/write without delete is insufficient |
| `not a git repository`, a wrong remote, or an absent or mismatched local identity | Repository configuration | Inspect `git status`, `git remote -v`, and repository-local config. Repair only the declared bindings; do not treat configuration as an authentication failure |

For `.git/index.lock`, first check whether the file exists and whether a git process is
using it. Remove only that exact, confirmed stale lock when permitted; otherwise ask the
owner to remove it in the host terminal. Never recursively change `.git/` permissions or
delete other lock files speculatively. A checkout the owner created does not give the
agent remote credentials; later fetch or push operations may need the same host-side
handoff.

## The check

```sh
python3 <itakua-sync>/scripts/check-sync.py
```

Run from the brain root. It reads the Sync row, works out what is actually carrying the
folder, and reports the difference: a declared `none, deliberately` with any sync in
sight is a problem. For git it compares remote and identity with the bindings, probes the
ignore rules (inbox binaries, `docs/drive`, `.drive-map.local`, `status.html`), lists the
files that exist only on this machine, and warns on tracked files over 1 MB in a slot. For
Syncthing it reads `.stignore` for the same exclusions. For Dropbox it reads the ignore
attribute on each `docs/drive` where it can. It lists conflict copies for every tool. A
query that fails is reported as not checked, never as an all-clear. Text only: it writes
nothing.
