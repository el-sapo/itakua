---
type: readme
domain: <domain>
date: <YYYY-MM-DD>
tags: []
# artifacts:                  # uncomment once docs/drive is linked -- see itakua-map
#   provider: google-drive
#   root: My Drive/<folder>   # the Drive folder docs/drive points to, as Drive shows it
---

# <Node name>

> **This folder is a node in an Itakua brain.** Load the `itakua-map` skill before working
> here — it defines the structure and the filing rules. If you cannot load it, say so
> rather than inferring the structure from what you see.

<!-- Folder name: lowercase, kebab-case if multi-word. Name it what you actually call it —
     Spanish or English, whichever you think in. -->

## What this is

<One paragraph: what this node is for, and what "healthy" looks like.>

## Structure

| Folder | What goes here |
|--------|----------------|
| `notes/` | Distilled knowledge. Mutable with owner approval as understanding improves. |
| `log/` | Dated raw evidence. Append-only; correct by adding a later entry. |
| `docs/` | *Optional.* Cloud-synced artifacts + generated `index.md`. Durable writes require owner approval. Once `docs/drive` is linked, declare its Drive folder in the `artifacts:` frontmatter key. Remove this row if unused. |
| `inbox/` | Captured, not yet filed. Anyone may add; text is tracked, other files stay on this machine. Nothing here is a source, nothing processes it unattended, and removing an item needs owner approval. |
| `<child>/` | *Optional.* A nested node with its own `README.md` — e.g. a project inside a space. |

> A folder is either a **slot** (the four above) or a **child node** (it has a `README.md`).
> Anything else is **limbo**: the owner's own space, which agents leave alone. Subfolders
> *inside* a slot are just filing and need no explanation — `notes/discovery/` is
> obviously notes.

<!-- inbox/ follows the default contract in the itakua-map skill: manual, on request,
     nothing removed without owner approval. Declare a narrower subfolder contract or a
     non-manual mode here only with owner approval; silence never grants either. -->

## Conventions

- **What this node's own slots hold:** <the cross-cutting layer — what spans its children.
  e.g. "method that generalises across clients"; "what applies across repertoire, gear and
  theory". If it has no children yet, say "everything about <node>, until it grows children">
- **Does this node end?** <"No — ongoing." | "Yes — finished when <X>, signed off by <who>.">
  Nesting says nothing about this; declare it here.
- Sub-work stays as subfolders in `notes/` unless it has **its own dated stream** — its
  own sessions or decisions that would clutter this node's `log/`. Then it earns a node.
- `domain:` in frontmatter is always the **top-level space**, never this node's name.

- File naming: <e.g. `NN-topic.md`, or `YYYY-MM-DD-topic.md` in `log/`>
- How much raw to keep in `log/`: <summaries, or full sources? The skill's "How much raw
  to keep" gives the two tests — accountability and re-interpretation. Keep the raw only
  if one of them passes; default to the distillate. Whatever enters `log/` is preserved
  as append-only evidence>
- <anything else an agent should know before touching this folder>


## Open threads

- <what's in flight>
