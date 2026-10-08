# Itakua

Itakua is an operating framework for personal knowledge bases built from nested nodes,
four predictable slots, and a small set of validation and setup tools. A brain is a
folder of plain markdown; it needs no sync, and takes any. The plugin ships three skills
with distinct triggers:

- `itakua-map` defines normal operation: where material belongs, when work earns a node,
  approval boundaries, node creation, validation, and artifact indexing.
- `itakua-setup` creates a brain and brings a copy into working order on a machine,
  including `docs/drive` attachments.
- `itakua-sync` owns whatever carries a brain between machines: git, Syncthing, Dropbox,
  iCloud, or none, deliberately. One table says what each tool may carry; its check
  compares the brain with what its README declares.

## What it gives you

- `itakua-setup/scripts/new-brain.sh` creates a brain: a plain folder with `spaces/`,
  `00-inbox/`, a README with the bindings table, an `AGENTS.md` pointer and `drive-map`.
- `itakua-map/scripts/new-node.sh` creates `notes/`, `log/`, and `inbox/` for a node and
  installs its README template without overwriting existing files.
- `itakua-map/scripts/check-structure.py` validates nodes, local artifact reachability,
  and each linked node's declared Drive root and link. It reports limbo, inbox counts and
  undistilled log entries; with `--report` it writes the same as a static `status.html`
  page at the brain root. Structure only: it never asks a sync tool anything.
- `itakua-map/scripts/index-artifacts.py` generates an approved index of cloud artifacts,
  with Drive links where this machine can read them.
- `itakua-setup/scripts/link-drive.sh` combines portable `drive-map` knowledge with
  machine-local cloud paths to recreate mapped `docs/drive` symlinks.
- `itakua-sync/scripts/check-sync.py` reads the README's Sync row, finds what actually
  carries the folder, and reports the difference: git remote, identity and ignore rules,
  Syncthing's `.stignore`, Dropbox's ignore attribute, conflict copies, and a brain
  declared as never synced that sits inside a synced folder.

The default safety contract is explicit: `inbox/` holds captured material that is not a
source yet; nothing processes it unattended, and nothing is removed without owner
approval. Capture tools (Dictalo, an agent saving a chat, a web clipper) write into the
brain's root `00-inbox/` under the same contract; agents move an item into a node or mark
it distilled only when asked. The loose capture format is in `itakua-map`, under
**Captures**. Any other folder inside a node is limbo, the owner's space, which agents
leave alone. Agents need approval before editing `notes/` or creating/editing durable
`docs/` content. Logs remain append-only raw evidence, with corrections added as new
entries. No sync ever carries `docs/drive`.

## Install with Claude

```sh
claude plugin marketplace add el-sapo/itakua --scope user
claude plugin install itakua@itakua --scope user
```

Restart the session after installation. Skills install per agent account, not per machine.

## Install with Codex

```sh
codex plugin marketplace add el-sapo/itakua
codex plugin add itakua@itakua
```

Start a new Codex task after installation. Both hosts discover the three skills from
`plugins/itakua/skills/`.

## Start a brain

```sh
<plugin>/skills/itakua-setup/scripts/new-brain.sh ~/Documents/mybrain "My Brain"
```

That is a complete setup. Load `itakua-sync` to carry it between machines; use
`--local-only` for a brain whose material must never leave the machine. The supported
bootstrap path is installing the plugin; generated brains do not carry a framework copy.

On another machine, load `itakua-setup` and ask the agent to bring the copy into working
order. For normal filing and node work, load `itakua-map`.

## What it is not

Itakua is not a note-taking application or sync service. A brain binds its own local
path, sync, cloud-storage account, and agent account, and declares them in its README.
