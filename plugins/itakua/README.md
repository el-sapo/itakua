# Itakua

Itakua is an operating framework for personal knowledge bases built from nested nodes,
four predictable slots, and a small set of validation and setup tools. The plugin ships
two skills with distinct triggers:

- `itakua-map` defines normal operation: where material belongs, when work earns a node,
  approval boundaries, node creation, validation, and artifact indexing.
- `itakua-setup` creates brains and repairs machine-local setup after a clone or move,
  including Git identity and `docs/drive` attachments.

## What it gives you

- `itakua-setup/scripts/new-brain.sh` creates a brain with a `spaces/` content container,
  bindings table, Claude and Codex pointers, protective ignore rules, and a Git repository
  with no remote.
- `itakua-map/scripts/new-node.sh` creates `notes/`, `log/`, and `inbox/` for a node and
  installs its README template without overwriting existing files.
- `itakua-map/scripts/check-structure.py` validates nodes, local artifact reachability,
  each linked node's declared Drive root, and the brain's declared Git bindings. It also
  reports limbo, inbox counts, and the files that exist only on this machine.
- `itakua-map/scripts/index-artifacts.py` generates an approved index of cloud artifacts,
  with Drive links for Google pointer files.
- `itakua-setup/scripts/link-drive.sh` combines committed `drive-map` knowledge with
  machine-local cloud paths to recreate mapped `docs/drive` symlinks.

The default safety contract is explicit: `inbox/` holds captured material that is not a
source yet; text there is tracked, other files stay on the machine, nothing processes it
unattended, and nothing is removed without owner approval. Any other folder inside a node
is limbo, the owner's space, which agents leave alone. Agents need approval before
editing `notes/` or creating/editing durable `docs/` content. Logs remain append-only raw
evidence, with corrections added as new entries.

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

Start a new Codex task after installation. Both hosts discover `itakua-map` and
`itakua-setup` from `plugins/itakua/skills/`.

## Start a brain

```sh
<plugin>/skills/itakua-setup/scripts/new-brain.sh ~/Documents/mybrain "My Brain" \
  --identity "Your Name <you@example.com>"
```

Use `--local-only` when a brain must never have a hosted remote. The supported bootstrap
path is installing the plugin; generated brains do not carry a second framework copy.

For a fresh clone, load `itakua-setup` and ask the agent to bring the checkout into working
order. For normal filing and node work, load `itakua-map`.

## What it is not

Itakua is not a note-taking application or sync service. A brain binds its own local path,
Git identity and remote policy, cloud-storage account, and agent account.
