---
name: itakua-map
description: The foundational map for operating an Itakua knowledge base built on spaces, nested nodes, four slots (notes/ log/ docs/ inbox/), and per-node READMEs. Load this before reading, writing, filing, or creating anything inside an Itakua brain or a folder whose README says it is a node. It defines where files go, when work earns a node, how content migrates, and which actions require owner approval.
---

# Operating an Itakua brain

Itakua is a personal knowledge system: **distilled knowledge in git as markdown, binary
artifacts in cloud storage, and procedures as skills.** Your job inside it is to file
things where they belong and keep the distinctions intact — the structure is load-bearing,
not decorative.

**Read the local `README.md` before working in any folder.** Structure is declared
per-node, not globally. This skill tells you how the system works; the node's README tells
you what *that* node is and what its own slots hold.

If the brain is being created, has just been cloned or moved, or reports a missing local
attachment or Git identity, load `itakua-setup` after this map. That
skill owns machine setup and repair; return here for normal operation.

## Nodes

Any folder with a `README.md` is a **node**. Nodes nest, and every node — at any depth —
has the same shape.

**Nesting expresses containment, not lifecycle.** A top-level node is a standing part of
someone's life. A nested node is a bounded unit *inside* one. That is all the nesting
means. Whether a node ever ends is a **property declared in its own README**, never
something you can read off its depth:

| Node | Nested? | Ends? |
|---|---|---|
| `guitar` | no | no |
| `gardening/huerta` | yes | **no** — a vegetable plot just goes on |
| `consulting/client-x` | yes | yes — the engagement gets signed off |

Do not import PARA here. PARA splits Projects from Areas *by lifecycle*; this splits *by
containment*, and a nested node is free to run forever.

## The four slots

```
<node>/
├── README.md   what this node is
├── notes/      what I know            → git, mutable with owner approval
├── log/        what happened          → git, append-only raw evidence
├── docs/       artifacts              → cloud storage, durable writes need approval
└── inbox/      captured, not filed    → git (text only); nothing here is a source
```

**A folder is either a slot (the four above) or a child node (it has a `README.md`).
Anything else is limbo** (see **Limbo** below). That one rule is what stops this
sprawling:

- **Subfolders inside a slot are just filing.** `notes/discovery/` needs no explanation —
  it is obviously notes. The taxonomy is the four slots; organising within them is free
  and silent. Do not give a subfolder a README to "explain" it.
- **Files that exist only on this machine are a category, not a bug.** A binary waiting
  in `inbox/` is one: git ignores it and the cloud does not hold it. The validator lists
  every such file so none of them is lost by surprise.
- **Portable core, machine-local edges.** `notes/`, `log/`, the text in `inbox/`, the
  READMEs and `drive-map` travel with the clone. `docs/drive` symlinks and the binaries
  in `inbox/` are per-machine. The validator makes a missing artifact attachment visible;
  the cloud data itself is not lost. A README's `artifacts:` key travels too: it is how
  readers that cannot follow the symlink learn where `docs/` lives in Drive (see
  **Frontmatter**).

`notes/` and `log/` are required. New nodes also create `inbox/`; existing or
deliberately minimal nodes may omit it. `docs/` is optional. A README lists only the
slots the node actually has.

### Limbo

Any folder inside a node that is neither a slot nor a child node is **limbo**. It is the
owner's playground: whatever they cannot or do not want to classify yet.

- Agents never create, move, tidy or delete anything in limbo, and never treat it as a
  source unless the owner points at it.
- Agents never stage it. **In a brain, stage by path, never `git add -A`** — whether
  limbo gets committed is the owner's call.
- `check-structure.py` reports a limbo folder as a note, never a failure. A `README.md`
  inside limbo gets a warning: a node must sit directly in a node, so that one is not
  validated.

Limbo exists only inside a node. A folder directly under `spaces/` without a README is
still a node missing its README, and the validator fails it.

## Where does this file go? — two questions

```
1. WHICH NODE?
   about one child specifically ............ that child
   spans several children, or the whole .... this node
   (no children? ........................... this node)

2. WHICH SLOT?
   a dated thing that happened ............. log/
   something I know ........................ notes/
   a binary artifact ....................... docs/
   captured, not yet distilled ............. inbox/
```

Question 1 is the one that goes wrong. **A parent's slots are not leftovers and not a
dumping ground — they are the cross-cutting layer.** A guitar node's `notes/` holds what
applies across repertoire, gear and theory; a fact about one song belongs to the song's
node, or to a subfolder of `notes/` if that node does not exist yet.

**Every node's README states its own cross-cutting scope** under Conventions. Read it
rather than guessing what "spans" means there.

Three edges that come up:

- **Does it generalise?** Ask: *would this still be true for a different song / client /
  plot?* If yes it belongs to the parent — **regardless of where you learned it**. A fact
  discovered while working on one song is not thereby a fact about that song.
- **Spans some but not all children?** Parent. The test is not *"does it cover
  everything"*, it is *"is it only about one child?"*
- **Part general, part specific?** Split it. The general statement goes up, the specific
  stays below. Lifting is distillation, never duplication — never leave two copies saying
  the same thing.

## Content migrates, in both directions

| | When | What moves |
|---|---|---|
| **Lift up** | Something turns out to generalise | Propose the general statement for the parent, stripped of specifics. After owner approval, move it; the concrete instance stays below as the worked example. Raise the proposal when you notice it rather than losing it in a node nobody reads |
| **Push down** | A new child node is created | Parent content that is *only* about that child moves into it. Creating a child is not `mkdir` — it is a re-sort of the parent |

Skipping the push-down is what decays a parent's slots into leftovers. It is the step that
gets forgotten.

## When does work become a node?

The test is **does it have its own dated stream?** — its own sessions, interviews or
decisions that would otherwise clutter the parent's `log/`.

| Example | Verdict |
|---|---|
| A client engagement — own interviews, own decisions, own end | **node** |
| "the calendar quick-win for that client" | **subfolder** in the client's `notes/` — its events belong in the client's log |
| A garden plot with its own planting log | **node** |
| A recurring topic like "triads" | **subfolder** in `notes/` |

**Bias towards not promoting.** A subfolder can be promoted later by adding a README and
slots; demoting a node means unpicking paths and references. When unsure, leave it as
filing.

**Depth:** two levels is the expected shape. Deeper is permitted but should be rare — if
you reach for a third level, say why in that node's README.

## Work *product* does not live here

The brain holds **knowledge about** work, not the work itself.

| Thing | Where |
|---|---|
| Knowledge, decisions, plans, research | `notes/` |
| Deliverable software for a client | **its own repo**, linked from `notes/` |
| Binary artifacts, exports, scans | `docs/` |

Client software has a different lifecycle, different collaborators and different
permissions from a personal knowledge base. Keeping it out is deliberate — **do not add a
fifth slot for it.**

## Why `log/` is never rewritten

Notes are rewritten by an LLM *by design* — that is the point of the system. Rewriting is
lossy: whatever the model judged redundant is gone. Two things make that safe.

**Logs are the source you distil from.** If a note loses a detail, the raw is still there.
Git history can recover deleted text, but nobody greps git history — agents read present
files. Logs are *queryable* history; git is *recoverable* history. Different jobs, and
only one is reachable at read time.

**Provenance.** A claim in `notes/` is auditable only while its source survives.

**Logs are append-only raw evidence.** Correct a log by appending a new entry that points
back to the original. Do not edit, replace, or delete an existing log entry. If the owner
explicitly requests destructive log removal, stop and show the exact proposed deletion.

### An auto-summary is not a source

A platform's automatic summary is already a distillation, made by something that did not
know what mattered here. Distil from the **transcript**; use the summary as an index to it.
Whatever the summary dropped is gone, and whatever it merged stays merged — and it says
neither. This holds even when the raw source is going to be discarded afterwards.

### How much raw to keep — two tests

Keep the raw source only if **one** passes:

| Test | Means |
|---|---|
| **Accountability** | Someone may challenge a claim and you need the receipt. Client work, money, consequences |
| **Re-interpretation** | New information changes what the old source *means*, so you go back and re-read it. Iterative discovery |

Lesson transcripts usually fail both — nobody audits what a teacher said, and lesson five
never sends you back to lesson two. Client interviews usually pass both.

**The asymmetry is not *whether* you preserve — it is *down to which layer*.** One node
keeps the distilled knowledge plus a thin dated index; another keeps the full transcript
as evidence. **Default to the distillate.** "We keep the source here" should be a
deliberate statement in the node's README, not an unexamined habit.

**When the raw is discarded, the distillate must be correct at the time of writing** —
there is no going back. If transcription is involved, correct known errors as you go and
mark what stays genuinely unclear rather than guessing.

An empty `log/` is an **invitation, not waste**. Without one, a dated entry has nowhere
obvious to go, lands in `notes/`, and corrupts the one distinction the spine rests on.

## `inbox/` — captured, not filed

`inbox/` is where anything meant for this node waits to be distilled: a file the owner
wants to add, a clipped page, a dictated note, a note typed on the fly. Capture tools
write here, so every node has a predictable place to receive material.

- **Nothing in `inbox/` is a source.** It is unreviewed. `notes/` never cites it, and a
  claim distilled from it cites the `log/` entry the distilling produced.
- **Anyone may add. Nothing processes it unattended.** Removing an item needs owner
  approval.
- **Subfolders are allowed** and follow the same rules.

It is the one slot whose contents have no fixed meaning yet, so it is the one slot with a
contract. The default lives here, not in each README:

- **Trigger:** the owner explicitly asks an agent to work on an inbox item.
- **Action:** do only the requested processing; otherwise leave the folder untouched.
- **Output:** the distill flow below; durable output only with owner approval.
- **Disposition:** keep the item unless the owner approves its exact removal.
- **Mode:** manual, on request. Scheduled and unattended passes do not touch it.

A node README declares an inbox contract only to narrow it for a subfolder (a
transcription drop, say) or to allow a non-manual mode. Both need owner approval, and
silence never grants automation or removal rights.

### Distilling out of the inbox

On request only:

1. **Confirm the node.** An item in a node's inbox may still generalise to the parent or
   belong to a child; ask the two filing questions again.
2. **Write the dated `log/` entry.** Keep the raw in `log/` only if it passes the
   accountability or re-interpretation test (see **How much raw to keep**); otherwise a
   thin entry.
3. **Propose the `notes/` changes** and wait for approval.
4. **Set `distilled_into`** on the log entry.
5. **Ask before removing the inbox copy.**

### Binaries in the inbox

**Text is tracked, binaries are not.** The brain's `.gitignore` uses an allowlist inside
every `inbox/`: `.md`, `.txt`, `.html` and `.gitkeep` are tracked, every other file stays
on this machine. An allowlist, because an inbox accepts any file, and no denylist keeps up
with `.heic`, `.webp`, `.epub` and whatever comes next.

```gitignore
**/inbox/**
!**/inbox/**/
!**/inbox/**/*.md
!**/inbox/**/*.txt
!**/inbox/**/*.html
!**/inbox/**/.gitkeep
```

`new-brain.sh` writes this block, plus the same for `/00-inbox/`. A brain that predates it
gets the block added by hand; the validator warns when a binary in an inbox would be
committed.

When distilling a binary, tell the owner it exists only on this machine and recommend
moving it to `docs/drive`. That is the expected workflow. Committing it with
`git add -f` stays possible as an explicit owner override, and it is one of the cases
that get a second ask (see **When the user overrides a rule**): history is permanent.

### Legacy `_tmp/`

Before 0.5.0 the fourth slot was `_tmp/`, gitignored manual staging. It is not renamed.
`_tmp/` stays in `.gitignore`, so nothing sitting there is committed by accident;
`inbox/` starts empty and the owner moves items across by hand. The validator reports a
leftover `_tmp/` as a legacy note and no longer asks for its contract.

## The repository root

The four slots are **per node**. The root is not a node and has no slots. What may sit
there is short and fixed:

| At the root | What it is |
|---|---|
| `spaces/` | **Required.** All content; every node lives under it. `check-structure.py` refuses to run without it |
| `00-inbox/` | Optional capture — anything not yet filed |
| `README.md` | What this brain is, its **bindings table**, and how to stand it up from a clone |
| `CLAUDE.md` / `AGENTS.md` | Three-line pointers to `README.md`. Pointers, never copies |
| `drive-map` | Optional committed mapping from node paths to artifact paths relative to the cloud root |
| `.drive-map.local` | Optional gitignored absolute overrides for this machine only |
| `status.html` | Optional, gitignored. The brain status page `check-structure.py --report` writes; generated per machine, never edited or committed |
| `.gitignore` | |

Anything else at the root is drift. `check-structure.py` only walks `spaces/`, so nothing
catches it for you. **A dated event or a piece of knowledge never belongs at the root** —
it belongs in a node, which is what the two filing questions are for.

### `00-inbox/`

Capture now, file later — for material that has no node yet. It takes anything, in any
shape, and **it is not a slot**: it has no meaning of its own, nothing is a source while it
sits there, and nothing may live there permanently. Filing out of it means answering the
two questions and moving the file into a node. It keeps text the way `inbox/` does: the
same allowlist tracks `.md`, `.txt` and `.html`, and leaves every other file on this
machine. A capture may carry its destination in front matter, as the capture format
defines.

Two limits, stated rather than implied: **nothing empties it on a schedule**, and
`check-structure.py` only counts it — items and the oldest one, as for a node's inbox — and
never files anything out of it. If a brain has no `00-inbox/`, do not create one to park
something you have not worked out where to put. Work out where to put it.

## Creating a node

**Naming:** lowercase, kebab-case if multi-word. **Name it what the owner actually calls
it** — in whichever language they think of it. Repos are often deliberately mixed; the
node name follows the work, as the content does. Do not name a node, or a filing
subfolder, `inbox`: git cannot tell it from the slot, so the inbox allowlist would leave
anything but text in it untracked.

**Language of what you write:** match the node. If a node's existing notes and logs are in
Spanish, write Spanish; if English, English. Read one existing file before writing your
first. A node's language belongs to the work happening in it — do not impose the language
of the framework, or your own default, on someone's material.

**The first node in a new brain has nothing to match**, and neither does the first node
with no sibling. The rule bottoms out, so do not quietly fall back to the framework's
language: **ask the owner what language this node's material will be in.** One question,
asked once per node, and worth asking because every later file matches the first.

**A new top-level node:**

1. Run `new-node.sh spaces/<name>` or copy the whole template directory bundled here at
   `assets/template/` to the new path. This creates `notes/`, `log/`, and `inbox/` by
   default.
2. With owner approval, fill every `<placeholder>` in its durable `README.md`. Leave the
   commented `artifacts:` key commented until the node's `docs/drive` is linked.
3. State in Conventions **what this node's own slots hold** once it has children. This is
   the sentence every future agent reads to decide where things go.
4. State whether it ends. Most do not.
5. Nothing else registers it — a directory listing is the truth. Do not edit a root file
   to add it.
6. Run the validator (see **Bundled tooling**).

**A new child node:**

1. Confirm it earns a node — **own dated stream?** If not, make it a subfolder in the
   parent's `notes/`.
2. Scaffold the template at `<parent>/<name>`; it includes `notes/`, `log/`, and `inbox/`.
3. With owner approval, fill in its README.
4. **Re-sort the parent.** After owner approval, move anything in the parent that is only about this child into
   it.
5. Add a row for it in the parent's README structure table.
6. **Rewrite the parent's "what this node's own slots hold" line.** A childless node
   usually says *"everything about X, until it grows children"* — which becomes false the
   moment you create one.
7. Run the validator (see **Bundled tooling**).

**A node for the brain itself.** Brain scaffolding does not create one. Create
it — `spaces/itakua/`, or whatever the owner calls the system — the first time the brain
produces evidence about *itself*: a recurring override, a decision about the framework, a
test of the structure. It earns a node by the usual test, its own dated stream, and until
that happens it does not need one. This is the node the override rule below means by *"the
second brain's own node log"*.

## Frontmatter

```yaml
type: note | log | readme | research | decision | idea
domain: <top-level node name>    # ALWAYS the top node, never a nested one
date: YYYY-MM-DD
tags: []
distilled_into: []   # log entries only — the notes this event produced
```

**There is no `status:` field, and adding one back needs a reason.** It was tried: every
one of the 33 files that carried it said `active`, so it distinguished nothing and
trained readers to skip the frontmatter it sat in. It was also the last piece of a
project-lifecycle model this framework does not use — nesting is containment, and
whether a node ends is its own declaration, not a field. A node that has gone quiet says
so in its README's opening line, where it can also say since when and why. Add the field
back only when a script actually needs to read it, and only where that script looks.

`domain:` stays coarse — a file inside `spaces/consulting/client-x/` carries
`domain: consulting`. The path already says which node it is in; `domain` exists to group
across the repo, so its set of values stays small.

Keep frontmatter flat. Complex YAML is a known parse-failure source. The one exception is
`artifacts:` below: a fixed two-field block on node READMEs. Nothing else nests.

### `artifacts:` — where a node's `docs/` lives in Drive

A node README whose `docs/drive` is linked declares the Drive folder behind it:

```yaml
artifacts:
  provider: google-drive
  root: My Drive/Guitarra
```

**Why it exists.** Only the owner's machine can follow `docs/drive`. The symlink is
per-machine, git ignores what it holds, and the Reader and every agent reading the brain
through the read-only MCP server get notes and READMEs, never `docs/`. Only Drive can
open those files. Without the key, an agent has to infer from README prose which Drive
folder `docs/` is, then hunt for a cited file by title. With it, the handoff is explicit:
an agent with its own Drive connector opens a cited artifact there, and that is intended.

- **Optional.** Only a node with a `docs/drive` link carries it. Every other node omits
  it — no empty `artifacts:`.
- `provider` is `google-drive`, the only store the framework defines.
- `root` is the Drive folder this node's `docs/drive` points to, written as a person sees
  it in Drive: from `My Drive` or `Shared drives` down, never a machine path. It is the
  mapping `link-drive.sh` applies from `drive-map` and `.drive-map.local`, so
  `check-structure.py` proposes the value from this machine's mapping and warns when the
  key and that mapping disagree. Quote it when the folder name holds `: ` or ` #`
  (`root: 'My Drive/Setlist #2'`); the validator's proposal already does.
- The key travels with the clone; the link does not. A fresh clone with the key and no
  link is the cue to load `itakua-setup`.
- Writing it is a README edit, so it needs owner approval.

## Citing an artifact

Nothing but Drive opens `docs/` (see `artifacts:` above), so how a note cites an artifact
depends on whether anyone will want to open it.

- **A reader or agent will want to open it** — a tab to play from, an inventory to check,
  a contract to read: the citation carries the Drive URL. Make the `docs/` path the link
  text, so one citation says both where the file sits in the tree and where to open it:

  ```markdown
  Full tab in [`docs/drive/songs/rock esp/El pibe de los astilleros.docx`](https://drive.google.com/file/d/<id>/view).
  ```

  Linking the title instead — `[My Gear.docx](https://drive.google.com/open?id=<id>)` —
  also meets the rule. Prefer the path when you know it: a reader can join it to the
  node's `root` and name the folder.
- **It is only context** — provenance, the source a note was distilled from: a path-only
  citation is fine.

Take the URL from the generated `docs/index.md`, which carries it for Google pointer files,
from Drive's *Copy link*, or from an agent's own Drive connector. Never build one from a
guessed id. Adding a URL to an existing note is a `notes/` edit and needs owner approval.

## When a node goes dormant

Some nodes end, some go quiet, most keep going. The trigger is the node's own definition
of done, if it declared one. If it never ends, none of this runs.

1. Say so in the first line of the node's README — dormant since when, and why. Prose,
   not a field: it survives being read by a human and cannot go quietly stale.
2. Write a final `log/` entry — delivered, decided, left open.
3. **Lift the generalisable part up** into the parent's `notes/`, stripped of specifics.
   The concrete instance stays as the worked example.
4. **Leave the folder where it is.** Do not move, rename or delete — git has the history,
   references keep working, and a dormant node is still readable.

There is deliberately no archive folder. If a dormant node ever crowds the working
context, that is the moment to build one — not before.

## Standing rules

- **Never commit binaries** (audio, PDF, images, video) — they belong in `docs/`. A
  binary in `inbox/` stays local until it moves there; `git add -f` is an owner override
  that gets a second ask.
- **Stage by path, never `git add -A`.** Limbo, and anything else the owner has not
  decided to commit, stays out of the index unless they say otherwise.
- **Durable writes need owner approval.** Creating or editing `README.md`, `notes/`, or
  anything under `docs/` requires approval. `docs/index.md` is generated, but regenerating
  it is still a durable write and must be requested or approved.
- **Nothing goes directly in `docs/` except `*.md`.** Files parked in `docs/` but outside
  the cloud-synced subfolder are gitignored *and* outside cloud storage — they exist in
  **no** system and have no backup. `scripts/index-artifacts.py` flags these; heed it.
- Before writing under `docs/`, check the local mirror is fresh — compare local mtime
  against the cloud copy's modified time. **If the cloud is newer, wait.**
- **A `log/` entry that produced knowledge says so.** `distilled_into:` lists the notes
  it fed. It is the link from event to knowledge, but the reason it earns its line is the
  empty case: **`distilled_into: []` means considered, nothing to lift**, while a *missing*
  field means nobody has looked yet. So `grep -rL --include='*.md' distilled_into log/` is
  the whole distillation audit, and `check-structure.py` runs it for every node —
  undistilled material announces itself instead of waiting for someone to read every entry
  and notice. Anything deliberately left for later goes in the entry's own body, with the
  reason.
- **Nothing writes to `notes/` unattended.** A scheduled or automated pass may read
  anything. It may append a `log/` entry only when an owner-approved contract says so,
  and it never processes `inbox/` or touches limbo by default. Every
  change to `notes/` carries human approval. `notes/` is the layer the rest of the system
  trusts; a plausible claim that nobody approved is the one failure the design cannot
  absorb, because everything downstream treats `notes/` as settled. **Automation
  proposes; a person disposes.**
- Unattended runs may **read** `docs/` but may not create or edit durable docs without
  owner approval.
- **Logs are bulky.** A meeting transcript can run 40 KB. When wiring a project context,
  select `notes/` and the READMEs, not `log/`.
- `docs/index.md` is **generated** — never hand-edit it. It is written in the **node's**
  language, not the framework's.
- **`docs/pointers-ok.md` is the escape hatch for the pointer warning.**
  `index-artifacts.py` flags native Google files because they cannot be read on disk;
  listing one in backticks in that file marks it deliberate and silences it. Use it. A
  warning you always ignore trains you to skip the orphan check sitting next to it, and
  that one is about data with no backup anywhere.

## Bundled tooling

| Script | Does |
|---|---|
| `new-node.sh` | Safely scaffolds a node with `notes/`, `log/`, `inbox/`, and the README template, without overwriting existing files |
| `check-structure.py` | Validates every node and its local artifact attachment, warns when a linked node's README lacks the `artifacts:` key, declares it without a link, or names a `root` this machine's mapping contradicts (proposing the `root` from that mapping), **and** checks the repository's git state — remote, identity — against the bindings declared in the root README. Notes limbo folders, a leftover `_tmp/`, each node's inbox count and oldest item, and the files that exist only on this machine; warns on tracked files over 1 MB in a slot and on a `.gitignore` that would commit inbox binaries. A git query that fails or times out is a warning, and what it would have counted shows as not checked, never as zero. `--no-git` skips every git query. `--report` also writes `status.html` at the brain root: the same findings and counts per node, as one static page that opens offline; without it the validator writes nothing. Run after any restructure, and after anything that touches git |
| `index-artifacts.py` | Regenerates a node's `docs/index.md` from its cloud folder, in the node's own language. Flags orphans and cloud-pointer files that cannot be read on disk. Its Link column gives each Google pointer file its Drive URL; other files' cells stay empty rather than guessed |

These scripts live under this skill's `scripts/` directory. Resolve that directory for the
current command, run the scripts from the brain root, and never persist an installed-skill
or plugin-cache path in the brain. Creation and per-machine attachment scripts belong to
`itakua-setup`; do not duplicate them here.

## When the user overrides a rule

These rules exist to keep the structure coherent. They are not enforced against the person
whose brain this is. If the user asks for something a rule here forbids — appending a
correction to a `log/` entry, filing something where it does not belong, skipping a step — **say once why
the rule exists, then do what they asked.** Arguing the case is useful; refusing is not.

Two things still deserve a second ask, because a file edit cannot undo them: destroying
history, and putting binaries or confidential material somewhere it leaks — across the
git/cloud boundary (an inbox binary committed with `git add -f` is this case), or into a
shared or work account.

**An override is not a precedent.** Do the thing, and leave the rule standing. If the same
override keeps coming up, that is not licence to change the rule in the moment — **record
it in the second brain's own node log.** A recurring override is evidence about the
framework, and evidence is looked at deliberately, in one place, not acted on by whoever
happens to notice it.

## If you cannot do something

Say so rather than improvising. This system's failure mode is an agent inventing structure
that was already specified — a stated gap is always better than a confident guess.
