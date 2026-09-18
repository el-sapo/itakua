---
name: itakua-map
description: The foundational map for operating an Itakua knowledge base built on spaces, nested nodes, four slots (notes/ log/ docs/ _tmp/), and per-node READMEs. Load this before reading, writing, filing, or creating anything inside an Itakua brain or a folder whose README says it is a node. It defines where files go, when work earns a node, how content migrates, and which actions require owner approval.
---

# Operating an Itakua brain

Itakua is a personal knowledge system: **distilled knowledge in git as markdown, binary
artifacts in cloud storage, and procedures as skills.** Your job inside it is to file
things where they belong and keep the distinctions intact — the structure is load-bearing,
not decorative.

**Read the local `README.md` before working in any folder.** Structure is declared
per-node, not globally. This skill tells you how the system works; the node's README tells
you what *that* node is and what its own slots hold.

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
├── notes/      what I know        → git, mutable with owner approval
├── log/        what happened      → git, append-only raw evidence
├── docs/       artifacts          → cloud storage, durable writes need approval
└── _tmp/       manual staging     → neither, never processed automatically
```

**A folder is either a slot (the four above) or a child node (it has a `README.md`).
Anything else is temporary.** That one rule is what stops this sprawling:

- **Subfolders inside a slot are just filing.** `notes/discovery/` needs no explanation —
  it is obviously notes. The taxonomy is the four slots; organising within them is free
  and silent. Do not give a subfolder a README to "explain" it.
- **Files in neither git nor cloud are a category, not a bug** — that is `_tmp/` doing
  its job.
- **Portable core, machine-local edges.** `notes/`, `log/` and the READMEs travel with the
  clone. `docs/`'s symlink and `_tmp/` staging are per-machine. A machine missing them
  degrades gracefully; no knowledge is lost.

`notes/` and `log/` are required. New nodes also create `_tmp/` with the safe manual
contract below; existing or deliberately minimal nodes may omit it. `docs/` is optional.
A README lists only the slots the node actually has.

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
   staged for a person to review ........... _tmp/
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

## Contracts — only for `_tmp/`

`_tmp/` is the single place where a file's meaning is *not* fixed by the slot it sits in,
so it is the single place needing a declaration. Everywhere else the slot already says
what a file is.

A contract answers five things, and lives in the node's README:

```markdown
### `_tmp/` — manual staging

- **Trigger:** the owner explicitly asks an agent to inspect a staged item.
- **Action:** do only the requested processing; otherwise leave the folder untouched.
- **Output:** propose a destination and request approval before writing durable output.
- **Disposition:** keep the source unless the owner approves its exact deletion.
- **Mode:** manual/on request. Scheduled and unattended passes do not touch this folder.
```

This is a procedure **declared at the point of use**: a transcription skill knows *how*;
the README says *where, what to produce, and what to do with the original*.

This is the default contract for every newly scaffolded node. A node may add narrower
subfolder contracts, but silence never grants automation or deletion rights.

Two cautions:

- **Deletion must be explicit and human-confirmed by default.** A contract that deletes
  sources is one bug away from destroying the only copy.
- **State whether an unattended pass may act.** The safe default is always
  `Mode: manual/on request`; changing it requires explicit owner approval.

## The repository root

The four slots are **per node**. The root is not a node and has no slots. What may sit
there is short and fixed:

| At the root | What it is |
|---|---|
| `spaces/` | **Required.** All content; every node lives under it. `check-structure.py` refuses to run without it |
| `00-inbox/` | Optional capture — anything not yet filed |
| `README.md` | What this brain is, its **bindings table**, and how to stand it up from a clone |
| `CLAUDE.md` / `AGENTS.md` | Three-line pointers to `README.md`. Pointers, never copies |
| `skill/` | Only in a brain created with `--with-skill` |
| `.gitignore` | |

Anything else at the root is drift. `check-structure.py` only walks `spaces/`, so nothing
catches it for you. **A dated event or a piece of knowledge never belongs at the root** —
it belongs in a node, which is what the two filing questions are for.

### `00-inbox/`

Capture now, file later. It takes anything, in any shape, and **it is not a slot**: it has
no meaning of its own, nothing is a source while it sits there, and nothing may live there
permanently. Filing out of it means answering the two questions and moving the file into a
node.

Two limits, stated rather than implied: **nothing empties it on a schedule**, and
`check-structure.py` does not look at it. If a brain has no `00-inbox/`, do not create one
to park something you have not worked out where to put. Work out where to put it.

## Creating a node

**Naming:** lowercase, kebab-case if multi-word. **Name it what the owner actually calls
it** — in whichever language they think of it. Repos are often deliberately mixed; the
node name follows the work, as the content does.

**Language of what you write:** match the node. If a node's existing notes and logs are in
Spanish, write Spanish; if English, English. Read one existing file before writing your
first. A node's language belongs to the work happening in it — do not impose the language
of the framework, or your own default, on someone's material.

**The first node in a new brain has nothing to match**, and neither does the first node
with no sibling. The rule bottoms out, so do not quietly fall back to the framework's
language: **ask the owner what language this node's material will be in.** One question,
asked once per node, and worth asking because every later file matches the first.

**A new top-level node:**

1. Run `new-node.sh spaces/<name>` or copy the whole template directory — bundled here at
   `assets/template/`, and in a self-contained brain at `skill/assets/template/` — to the
   new path. This creates `notes/`, `log/`, and `_tmp/` by default.
2. With owner approval, fill every `<placeholder>` in its durable `README.md`.
3. State in Conventions **what this node's own slots hold** once it has children. This is
   the sentence every future agent reads to decide where things go.
4. State whether it ends. Most do not.
5. Nothing else registers it — a directory listing is the truth. Do not edit a root file
   to add it.
6. Run the validator (see **Bundled tooling**).

**A new child node:**

1. Confirm it earns a node — **own dated stream?** If not, make it a subfolder in the
   parent's `notes/`.
2. Scaffold the template at `<parent>/<name>`; it includes `notes/`, `log/`, and `_tmp/`.
3. With owner approval, fill in its README.
4. **Re-sort the parent.** After owner approval, move anything in the parent that is only about this child into
   it.
5. Add a row for it in the parent's README structure table.
6. **Rewrite the parent's "what this node's own slots hold" line.** A childless node
   usually says *"everything about X, until it grows children"* — which becomes false the
   moment you create one.
7. Run the validator (see **Bundled tooling**).

**A node for the brain itself.** Nothing creates one and `new-brain.sh` does not. Create
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

Keep frontmatter flat. Complex YAML is a known parse-failure source.

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

- **Never commit binaries** (audio, PDF, images, video) — they belong in `docs/`.
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
  field means nobody has looked yet. So `grep -L distilled_into log/*.md` is the whole
  distillation audit — undistilled material announces itself instead of waiting for
  someone to read every entry and notice. Anything deliberately left for later goes in the
  entry's own body, with the reason.
- **Nothing writes to `notes/` unattended.** A scheduled or automated pass may read
  anything. It may append a `log/` entry only when an owner-approved contract says so,
  and it never processes or writes `_tmp/` by default. Every
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

## Creating a new brain

A brain is an **instance** of this framework: its own folder, its own git repository, its
own bindings. That is a different job from creating a node, and it has its own script.

**First, and this is the step that gets skipped: install this skill on the account that
will operate the new brain.** A skill installs per agent **account**, not per machine. Two
brains on one computer run by two accounts need two installs, and the second account
starts with nothing. Nothing on disk does this for you. A brain stood up without it gets a
hand-built structure that looks right and carries none of the bindings below.

```sh
new-brain.sh <path> "<Name>" [--identity "Name <email>"] [--local-only] [--with-skill] [--into-existing]
```

| Flag | Does | When |
|---|---|---|
| `--identity` | Binds git identity **`--local`** to this repo | **Always**, on any machine with more than one brain. Validated — a malformed value is refused rather than silently committed |
| `--local-only` | Declares the brain never-published and records the boundary in its README | When the material must not reach a hosted remote. The *absence of a remote* is the actual control; this documents why, for whoever reads it later |
| `--with-skill` | Copies `itakua-map` into `skill/` | Keep for exceptional self-bootstrapping clones where marketplace installation is unavailable. It is not redundant, but it costs a second copy that can drift and leaves drift detection off until you install it and run `--stamp` |
| `--into-existing` | Scaffolds around what is already in the folder, **overwriting nothing** | When the destination is not empty. Without it the script refuses, which is the safe default |

It creates `00-inbox/`, `spaces/`, `.gitignore`, pointer files `CLAUDE.md` and `AGENTS.md`, and a `README.md`
carrying the **bindings table**: path, git remote, git identity, cloud storage, agent
account. Fill in the two it cannot know, and **mark which bindings are constraints and
which are preferences** — they look identical in a table, and a constraint you can relax
by accident is not one.

`check-structure.py` reads that table back off the README and compares it to the
repository, so the table is not decoration: it is what makes a wrong remote or a wrong
commit identity detectable. Then create the first node, above.

## Bundled tooling

| Script | Does |
|---|---|
| `new-brain.sh` | Stands up a **new brain**: spine, `.gitignore`, bindings table, git repo with no remote. See **Creating a new brain** |
| `new-node.sh` | Safely scaffolds a node with `notes/`, `log/`, `_tmp/`, and the README template, without overwriting existing files |
| `check-structure.py` | Validates every node, **and** checks the repository's git state — remote, identity — against the bindings declared in the root README. Run after any restructure, and after anything that touches git |
| `index-artifacts.py` | Regenerates a node's `docs/index.md` from its cloud folder, in the node's own language. Flags orphans and cloud-pointer files that cannot be read on disk |
| `link-drive.sh` | Creates each node's `docs/drive` symlink. **Run from a terminal**, once per machine |

**One set of files, wherever this skill happens to live.** Three possibilities, same files:

| Installed from | Scripts are at |
|---|---|
| A plugin | `${CLAUDE_PLUGIN_ROOT}/skills/itakua-map/scripts/` |
| A `.skill` file | `<installed-skill>/scripts/` |
| A brain repo that carries one | `skill/scripts/` |

The third exists because that repo's `skill/` directory *is* this skill, packaged from
there. If you cannot tell which applies, `find` the script by name rather than guessing.

**Always run them from the repository root**, whichever copy you invoke: they operate on
the current directory, not on where the script lives.

```sh
python3 skill/scripts/check-structure.py              # a repo that carries skill/
python3 <wherever-this-skill-is>/scripts/check-structure.py   # otherwise
python3 skill/scripts/index-artifacts.py spaces/<node>
```

**`skill/scripts/…` everywhere in this document is shorthand for whichever of those
applies.** If neither is reachable — in a session scoped to a single node, for instance —
say so rather than reimplementing them.

**The installed copy is per account.** `skill/.packaged` records a hash of every skill
file at packaging time and `check-structure.py` reports drift against it. That is one
stamp against however many accounts installed the skill: it cannot tell you account B is
stale. Re-package and re-install in **every** account, then run `--stamp`.

## When the user overrides a rule

These rules exist to keep the structure coherent. They are not enforced against the person
whose brain this is. If the user asks for something a rule here forbids — appending a
correction to a `log/` entry, filing something where it does not belong, skipping a step — **say once why
the rule exists, then do what they asked.** Arguing the case is useful; refusing is not.

Two things still deserve a second ask, because a file edit cannot undo them: destroying
history, and putting binaries or confidential material somewhere it leaks — across the
git/cloud boundary, or into a shared or work account.

**An override is not a precedent.** Do the thing, and leave the rule standing. If the same
override keeps coming up, that is not licence to change the rule in the moment — **record
it in the second brain's own node log.** A recurring override is evidence about the
framework, and evidence is looked at deliberately, in one place, not acted on by whoever
happens to notice it.

## If you cannot do something

Say so rather than improvising. This system's failure mode is an agent inventing structure
that was already specified — a stated gap is always better than a confident guess.
