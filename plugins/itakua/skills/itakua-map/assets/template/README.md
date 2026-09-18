---
type: readme
domain: <domain>
date: <YYYY-MM-DD>
tags: []
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
| `docs/` | *Optional.* Cloud-synced artifacts + generated `index.md`. Durable writes require owner approval. Remove this row if unused. |
| `_tmp/` | Manual staging. No automatic processing and no deletion without owner approval. |
| `<child>/` | *Optional.* A nested node with its own `README.md` — e.g. a project inside a space. |

> A folder is either a **slot** (the four above) or a **child node** (it has a `README.md`).
> Anything else belongs in `_tmp/`. Subfolders *inside* a slot are just filing and need no
> explanation — `notes/discovery/` is obviously notes.

## `_tmp/` contract

`_tmp/` is the only place whose meaning is not fixed by the slot it sits in, so it is the
only place that needs declaring. An agent reads this and honours it.

### `_tmp/` — manual staging

- **Trigger:** The owner explicitly asks an agent to inspect a staged item.
- **Action:** Do only the requested processing; otherwise leave the folder untouched.
- **Output:** Propose a destination and request approval before writing durable output.
- **Disposition:** Keep the source unless the owner approves its exact deletion.
- **Mode:** Manual/on request. Scheduled and unattended passes do not touch this folder.

Add narrower subfolder contracts below only with owner approval. Silence never grants
automation or deletion rights.

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
