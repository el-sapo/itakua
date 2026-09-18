# Itakua

Itakua is an operating framework for personal knowledge bases built from nested nodes,
four predictable slots, and a small set of validation and setup tools. Its foundational
skill is `itakua-map`.

## What it gives you

- `new-brain.sh` creates a new brain with a `spaces/` content container, bindings table,
  Claude and Codex pointers, protective ignore rules, and a Git repository with no remote.
- `new-node.sh` creates `notes/`, `log/`, and `_tmp/` for a new node and installs the node
  README template without overwriting existing files.
- `check-structure.py` validates nodes and checks the brain's declared Git bindings.
- `index-artifacts.py` generates an approved index of cloud-stored artifacts.
- `link-drive.sh` links each node's `docs/drive` folder to cloud storage per machine.

The default safety contract is explicit: `_tmp/` is manual staging with no unattended
processing; nothing there is deleted without owner approval. Agents need approval before
editing `notes/` or creating/editing durable `docs/` content. Logs remain append-only raw
evidence, with corrections added as new entries.

## Install with Claude

```sh
claude plugin marketplace add <path-to-itakua>
claude plugin install itakua@itakua
```

Restart the session after installation. Skills install per agent account, not per machine.

## Install with Codex

```sh
codex plugin marketplace add <path-to-itakua>
codex plugin add itakua@itakua
```

Start a new Codex task after installation. Both hosts load
`plugins/itakua/skills/itakua-map/`.

## Start a brain

```sh
<plugin>/skills/itakua-map/scripts/new-brain.sh ~/Documents/mybrain "My Brain" \
  --identity "Your Name <you@example.com>"
```

Use `--local-only` when a brain must never have a hosted remote.

### Should you use `--with-skill`?

Usually, no: marketplace installation gives each agent account one maintained copy of
`itakua-map`. Keep `--with-skill` for a brain that must bootstrap itself from its own clone
when the marketplace is unavailable. The tradeoff is a second framework copy that can
drift and must be installed and stamped separately. The option is useful, but exceptional.

## What it is not

Itakua is not a note-taking application or sync service. A brain binds its own local path,
Git identity and remote policy, cloud-storage account, and agent account.
