# XFE-233 implementation plan: capture format v0

Linear: [XFE-233](https://linear.app/xfede/issue/XFE-233/itakua-skill-capture-format-v0-the-inbox-write-contract-for-dictalo).
Baseline: `main` 03df265, plugin 0.6.0, 80 tests green (`python3 -m unittest discover -s tests`).

The open questions are numbered **Q1–Q19**. The visual summary (the open-questions page) uses
the same numbers. This plan does not answer them. A step that depends on one is marked
**⛔ Qn** and describes only what holds under every option. **✅** means the step can start now.

---

## 1. Summary

- **Ships:**
  - `docs/capture-format.md` (v0) with four fixtures, one per kind;
  - a `### Captures` subsection in itakua-map `SKILL.md`, plus the edits it forces elsewhere in
    that file;
  - in `check-structure.py`: a warning for malformed captures, silence for bare drops, and a
    **distilled / pending** status for each inbox item, derived from `captured_from:` in `log/`
    entries;
  - the status page showing that split; tests; a version bump.
- **Version:** the next minor (0.7.0). Every earlier feature release bumped the minor. Where the
  "CHANGELOG entry" lives is **Q19**.
- **Out of scope:** the MCP `capture` tool (XFE-196), Dictalo's writer (XFE-189), the later
  `check-capture` script, binaries through the protocol, unattended inbox processing, a Reader
  review queue.
- **State:** 19 open questions. None stops the groundwork in §5 phase 0. Producers (XFE-196,
  XFE-189) wait only on the producer-facing set (§5 phase 1).

### Settled by the ticket (checked, not open)

Verification raised these and closed them, because the ticket or the code already answers them.
The plan follows them as written:

| Topic | What the plan does |
|---|---|
| Spec link and versioning | The file on `main` of the public repo is "the one URL". A version line in the document carries the version. Additive keys and kinds stay v0 ("keys are additive", "unknown `kind` reads as `note`"). |
| 0.5.0 counts | Inbox count and Oldest age keep counting distilled items the owner has not removed ("Counts already shipped in 0.5.0 are unchanged"). The distilled/pending split appears **beside** them. |
| Text output | Every new number on the page is also printed in the text output (`check-structure.py` L51-53: "every number on the page is one the text output gave"). |
| MCP write scope | Decision 2 supersedes IR-041's "`00-inbox/` only". IR-041's scope, its exit "No request can create a file outside `00-inbox/`" and its security review are rewritten in Linear (W9). |
| To-check experiments | Investigations, not exit gates. The ticket's Exit list is separate. |
| "Keeps sources" | The ticket and SKILL.md L188-207 agree: lessons stay thin unless the node README says it keeps sources. |
| 1 MB cap | Producers enforce it. On the reading side, the existing `check_sizes()` (L303-317) already warns about tracked files over 1 MiB in a slot. No new consumer check. |
| Hostile files | No new rule. The validator must never crash (tests assert empty stderr), and the page escapes through `esc()` (L819). |
| Which files are read | Any file in an inbox that claims `type: capture` is checked. Read only its start, so large binaries are never read whole. |

## 2. Dependency map

```mermaid
graph LR
  X219["XFE-219 inbox slot (0.5.0) DONE"] --> X233["XFE-233 capture format v0"]
  X233 -- blocks --> X196["XFE-196 IR-041 MCP capture tool"]
  X195["XFE-195 read-only MCP server"] --> X196
  X196 --> X207["XFE-207 deployment kit"]
  X233 -- blocks --> X189["XFE-189 IA-039 Dictalo destination (M6, after v1)"]
  X233 -. same four fixtures .-> APP["Itakua app fixture set (IA, M0)"]
  X222["XFE-222 brain migration (owner, Backlog)"] -. brains on the 0.5.0 slot .-> X233
```

| Relation | Ticket | Effect on this work |
|---|---|---|
| Relies on, shipped | XFE-219 | `inbox/` slot, the allowlist (`new-brain.sh` L120-136), the inbox counts in `check_inbox` (L201-229). These counts stay as they are. |
| Relies on, not done | XFE-222 | The personal and Globant brains are not migrated yet. The exit test's "iCloud Learning brain" is not covered by XFE-222 (**Q17**). |
| Unblocks | XFE-196 | The MCP server implements the spec. It also needs **Q8**, **Q14** and **Q15**. |
| Unblocks | XFE-189 | Dictalo implements the spec in its own repo. It also needs **Q3**, **Q18** and **Q17**. |
| Feeds | Itakua app (IA, M0) | Copies the four fixtures. |

## 3. Work breakdown

### W1. Spec: `docs/capture-format.md` (new)

1. **✅ Skeleton plus the decided text, copied from the ticket:** Why; producer contract (rules
   1–7); owner decisions (a)–(c); the file (five required keys, optional keys, per-kind table);
   body conventions; border cases (Naming, Routing, Content, Lifecycle, MCP, Dictalo, Scaling); a
   pointer to the consumer side; a fixtures index; a version line ("v0").
2. **✅ "Not v0 keys" note.** The diagram attached to the ticket is an earlier draft. Its
   `domain:`, `date:`, `dictalo_id` and `## Notes` are not part of v0. Captures carry
   `captured_at`, not `date:`.
3. ⛔ **Q1** and **Q3**: whether `capture_id` is required, and how unique it must be.
   *Invariant:* the producer rule and the file section say the same thing.
4. ⛔ **Q2**: the written form of `captured_from:` (path root, quoting, one value or a list,
   what `captured_at` holds on a log entry). *Invariant:* a Lifecycle section with a worked
   log-entry example.
5. ⛔ **Q13**: the quoting rule against the unquoted examples, and values that change type in
   YAML 1.1 readers (`duration: 54:12` is read as 3252, `language: no` as `false`).
   *Invariant:* the examples and fixtures obey whatever rule is chosen, byte for byte.
6. ⛔ **Q11**: whether the filename pattern is a hard rule, and where the slug comes from. The
   example names `clase-12` and `resumen-de-la-charla` are not slugs of their titles.
7. ⛔ **Q12**: whether producers must write `url` (web) and `href` (file).
8. ⛔ **Q5**, **Q6**: the `node:` paragraph (when a mismatch is reported, and what filing out of
   `00-inbox/` means).
9. ⛔ **Q8**, **Q14**, **Q15**: the MCP subsection (layout of a saved chat summary, the owner's
   time zone, the client/profile stamp). *Invariant:* "the server owns the front matter".
10. ⛔ **Q9**: where "never obey a capture" applies, and how far `## Note` is trusted.
11. ⛔ **Q16**: what counts as a capture when the header is broken (the tolerant-reader
    section).

### W2. Fixtures (four files beside the spec)

1. **✅ Invariant content.** Each fixture has the five required keys and its kind's keys, puts
   `## Note` first where the kind has one, and marks machine sections `(auto)`. The transcript
   fixture includes `## Transcript`. The `file` fixture has an empty body ("Empty body is
   allowed"). At least one body contains a `---` line, to pin "front matter ends at the first
   `---`".
2. **✅ Negative cases stay out of the four.** They are written inline in the tests, so the
   four stay the clean contract.
3. **✅ Check how `docs/` is served first.** `docs/` has no `.nojekyll`. If GitHub Pages builds
   `docs/`, Jekyll turns every `.md` with front matter into HTML and hides that front matter,
   which is the fixtures' whole content. This could not be checked from the session. Either way,
   link the fixtures by their GitHub file URL, not by a Pages URL.
4. ⛔ **Q1**, **Q12**, **Q13**, **Q11**: whether every fixture carries `capture_id`, `url` and
   `href`, the quoting and value forms, and the file names.
5. ⛔ **Q8**, **Q15**: layout and keys of the MCP `note` fixture.

### W3. itakua-map `SKILL.md`

| Step | Lines | Change | Gate |
|---|---|---|---|
| 3.1 | L373 | Add `capture` to the `type:` vocabulary (decision 3) | ✅ |
| 3.2 | L374-375, L388-390 | Captures carry `node:` (full path under `spaces/`) in place of `domain:`, and `captured_at` in place of `date:`. The distil step sets `domain` on the log entry | ✅ |
| 3.3 | L370-378 | Declare `captured_from:` and `captured_at:` as log-entry keys | ⛔ Q2 (form) |
| 3.4 | new `### Captures` between L248 and L250 | The ticket's five bullets: bare drop vs capture; `## Note` as the owner's correction layer and `(auto)` as an index; provenance; the short-transcript flag; `web` keeps the URL | ⛔ Q10 (which spec rules are copied in), Q9 (trust), Q8 (MCP summaries), Q18 (short transcript), Q1 (capture with no id) |
| 3.5 | L237-248, distil flow | Step 2 writes provenance. Say when an item counts as distilled. Step 5 is unchanged | ⛔ Q2, Q4 |
| 3.6 | L304-307, `00-inbox/` | "moving the file into a node" against "no moves" | ⛔ Q6 |
| 3.7 | L309-310 | Change "as the capture format defines" to point at the Captures subsection and the spec URL | ✅ link; how much is copied in is ⛔ Q10 |
| 3.8 | L312-314 | "`check-structure.py` only counts it" stops being true once the validator reads, warns on and derives status for `00-inbox/` captures. Reword it | ✅ wording follows Q5 and Q7 |
| 3.9 | L504-511, standing rules | One sentence: `captured_from:` derives inbox status. The `distilled_into` audit stays unchanged | ⛔ Q4 (the word "distilled") |
| 3.10 | L536, bundled tooling | Describe the capture warning and the derived status | ✅ after W4 |

### W4. Validator: `plugins/itakua/skills/itakua-map/scripts/check-structure.py`

```
inboxes() L158 ─► inbox_items() L166 ─► capture_of(item): bare drop | capture
                                               └─► check_captures() ─► WARN (missing key, node:)
log/ walk (check_distilled L232) ─► Undistilled count (unchanged) + cited = {captured_from values}
                                               ▼
                         inbox_status() ─► distilled | pending per item ─► fact(node)["captures"]
                                               ▼
                                 text output lines  +  status.html
```

1. **✅ Answer To-check 3 (parser reuse).** Spike result:
   - `frontmatter()` (L415-423) and `scalar()` (L426-451) handle flat scalars. They read
     `"capture"` as `capture`, drop trailing comments and keep `dictalo:128` and
     `mcp:claude-ios:7f3a` intact.
   - Missing: a generic flat key reader (`declared_artifacts()` L465-491 reads one key only).
   - `check_distilled()` (L253) is a substring test, not a parse.
   - Block lists are not read.
   - A BOM before `---`, or a header that never closes, returns `[]`, so the file reads as a bare
     drop.
   - An unquoted `title: Clase 12: tríadas` returns `None`.
   - `...` also closes a header (L421), while the ticket says "the first `---`". Document this or
     align it, with a test.
   - The script cannot be imported (`sys.exit(main())` at L1130), which matters for the later
     `check-capture` script.

   Record all of this in the PR description.
2. **✅ `flat_keys(lines)`** next to `declared_artifacts()`. It reads top-level `key: value` lines
   through `scalar()` and skips indented and comment lines. Empty and unreadable values:
   ⛔ Q16.
3. **✅ Constants** near L40-47: `CAPTURE_REQUIRED = ("type", "source", "kind", "title",
   "captured_at")`. Per-kind keys: ⛔ Q12.
4. **✅ `capture_of(path)`.** Reads only the start of the file. Returns `None` for a bare drop,
   or the parsed keys for a capture. Read-only. Never raises (`errors="replace"`, catch
   `OSError`). Behaves the same with `--no-git`. Broken-header cases: ⛔ Q16.
5. **`check_captures(pairs)`**, called in `main()` right after `check_inbox` (L1097).
   - ✅ A file with a closed header and `type: capture` that lacks one of the five keys gets one
     `warn()` naming the file and the key. Attribution follows `check_inbox` (`node=key(n)`,
     `None` for `00-inbox/`). Warnings never change the exit code (L1127). Bare drops print
     nothing.
   - ⛔ **Q5**: the `node:` rule. *Invariant:* an inbox subfolder belongs to its inbox's node
     (contract rule 3), values are compared NFC-keyed (L74-76, L410-412), and `00-inbox/`
     fallbacks with `node:` set follow whatever Q5 decides.
6. **✅ One walk of the logs.** Extend `check_distilled` (L243-253) to parse each entry's front
   matter once and collect raw `captured_from` values. Keep `pending += "distilled_into" not in
   text` exactly as it is, so the 0.5.0 Undistilled count does not change. Normalising the value:
   ⛔ Q2.
7. **`inbox_status(pairs, cited)`** stores `fact(node)["captures"] = {"distilled": d,
   "pending": p}`.
   - *Invariant:* nothing is written into any inbox file. Citations count from every node's
     `log/` at any depth. Items in inbox subfolders are included. The 0.5.0 inbox count and
     oldest age are unchanged.
   - ⛔ Q1 (capture with no id), Q3 (two files with one id), Q2 (bare-drop path form), Q6 (a
     bare drop moved after distilling), Q7 (which row counts a root capture addressed to a
     node), Q4 (cited vs approved).
8. **Text output.** Print the split for every inbox that has items.
   - *Invariant:* the existing note `"<inbox>/: N item(s), oldest …"` (L229) stays
     byte-identical, with the split on its own line or appended after it. An empty inbox still
     prints nothing.
   - Tests that depend on this format: `test_inbox_slot.py` L167, L180, L189 (`assertNotIn("inbox/:")`
     for an empty inbox), L201; `test_status_page.py` L155, L166.
9. ✅ Update the module docstring (L1-36, especially L33-35).

### W5. Status page (render functions in `check-structure.py`, `assets/status-page.html`)

1. **✅ Show the split beside the existing counts:**
   - nodes table: `nodes_html` head at L949-950, `node_row` at L918-942;
   - Brain panel `00-inbox/` row: `brain_html` L1001-1002, `inbox_html` L961-972;
   - if tiles are added, the grid is fixed at `repeat(8, …)` (template L88), with 4 and 2 at
     L161 and L165.
2. ⛔ **Q4**: the labels, so "distilled" does not collide with the shipped "Undistilled" column.
3. ⛔ **Q7**: whether a root capture addressed to a node shows on that node's row.
4. **✅ Invariants:**
   - new values go through `esc()` (L819);
   - new numbers carry `data-count` / `data-total`, for the tests;
   - the page stays self-contained (`test_status_page.py` L101-111);
   - page numbers equal text numbers.

### W6. Tests — see §4.

### W7. Docs and READMEs

1. `plugins/itakua/README.md` L19-22 (check-structure bullet) and L29-34 (safety contract): one
   sentence each on captures and derived status. ✅
2. `README.md` L18-22 (the model): one line on captures, with the spec link. ✅
3. `docs/index.html` L231 (inbox paragraph): one sentence and a link to the spec. Check that the
   aria-label at L135 still holds. ✅ (respect W2.3)
4. `new-brain.sh`, `itakua-setup/SKILL.md`, template README: no change expected. Captures are
   `.md`, which the allowlist already tracks (`new-brain.sh` L127, L133). Verify only. ✅

### W8. Version and release

1. Bump `version` in `plugins/itakua/.claude-plugin/plugin.json` and
   `plugins/itakua/.codex-plugin/plugin.json` together, to 0.7.0. ✅
2. Release notes: ⛔ **Q19** (no CHANGELOG exists today).
3. Commit and PR title "… (0.7.0)", as in 8464c43 and 30a8876. ✅
4. Run the README validate block (README.md L46-52) before merging. ✅

### W9. Linear follow-ups (owner or PM, outside the repo)

1. XFE-196 / IR-041: point at the spec. Rewrite the scope, "Out of scope: writing anywhere other
   than `00-inbox/`", the exit "No request can create a file outside `00-inbox/`", and the
   security review, all per decision 2. Answers to Q8, Q14 and Q15 feed it.
2. XFE-189 / IA-039: point at the spec. Remove "only into `00-inbox/`" and "agreed in IR-041".
   Answers to Q3, Q17 and Q18 feed it.
3. Mark the attached diagram superseded, or redraw it. It shows `domain:`, `date:`,
   `dictalo_id`, `## Notes` and an unquoted title. ✅
4. Itakua app fixture set (IA, M0): copy the four fixtures in once merged.
5. New ticket for the `check-capture` script ("Scaling"). The validator cannot be imported today
   (W4.1).
6. Record the owner's confirmation of decisions 1–4. They are still "proposed" in the ticket. ✅

## 4. Test plan

A new module, `tests/test_captures.py`, built in the style of `test_inbox_slot.py`. It uses
temporary brains created by `new-node.sh` / `new-brain.sh`, a `validate()` helper that asserts
empty stderr, and `lines()`. It runs the public script and never imports it. It also extends
`tests/test_status_page.py`.

**A. Fixture contract**

| Test | Gate |
|---|---|
| `test_every_fixture_is_a_clean_capture`: each fixture copied into a node inbox gives no WARN or PROBLEM and counts as pending | ✅ (content gated by W2.4) |
| `test_fixtures_cover_each_kind_once` | ✅ |
| `test_removing_any_required_key_from_a_fixture_warns` (4 × 5) | ✅ for the five; per-kind keys ⛔ Q12 |
| `test_dash_lines_in_body_stay_body` | ✅ |
| `test_spec_and_validator_agree_on_required_keys`: reads the spec's key list from the doc | ✅ |

**B. Warnings and hostile input**

| Test | Gate |
|---|---|
| `test_bare_drop_is_silent` (`.md`, `.txt`, `.html`, `.heic`, no header) | ✅ |
| `test_front_matter_without_type_capture_is_silent` | ✅ |
| `test_missing_required_key_warns_once_per_file` | ✅ |
| `test_capture_warnings_never_change_exit_code` | ✅ |
| `test_unknown_kind_and_unknown_keys_are_silent` | ✅ for keys outside the per-kind table; per-kind ⛔ Q12 |
| `test_empty_body_capture_is_clean` | ✅ |
| `test_node_matching_its_inbox_is_silent` (including `inbox/dictalo/`) | ✅ |
| `test_undecodable_bytes_do_not_crash` | ✅ |
| `test_large_binary_is_not_read_whole` | ✅ |
| `test_capture_values_are_escaped_on_the_page` (pattern of `test_status_page.py` L175-184) | ✅ |
| `test_quoted_type`, `test_bom_header`, `test_unclosed_header`, `test_empty_or_unreadable_value`, `test_duplicate_keys` | ⛔ Q16 |
| `test_node_mismatch_in_node_inbox`, `test_root_inbox_capture_with_node`, `test_root_capture_for_a_missing_node`, `test_capture_moved_between_inboxes`, `test_node_nfc_vs_nfd` | ⛔ Q5 |

**C. Derived status**

| Test | Gate |
|---|---|
| `test_capture_cited_by_id_is_distilled` (`captured_from: dictalo:128`, the ticket's form) | ✅ |
| `test_uncited_capture_is_pending` | ✅ |
| `test_citation_from_any_node_and_log_subfolder_counts` | ✅ |
| `test_citing_entry_without_distilled_into_is_still_undistilled` (0.5.0 count unchanged) | ✅ |
| `test_inbox_count_and_oldest_include_distilled_items` (0.5.0 counts unchanged) | ✅ |
| `test_status_is_the_same_with_and_without_git` | ✅ |
| `test_report_never_touches_inbox_files` (bytes, `mtime_ns`, `git status` unchanged) | ✅ |
| `test_captured_from_variants`, `test_bare_drop_cited_by_path`, `test_bare_drop_path_nfc_vs_nfd` | ⛔ Q2 |
| `test_capture_without_capture_id` | ⛔ Q1 |
| `test_two_files_share_one_capture_id` | ⛔ Q3 |
| `test_bare_drop_moved_after_distilling` | ⛔ Q6 |
| `test_root_capture_addressed_to_a_node_is_counted_on` | ⛔ Q7 |
| `test_cited_but_not_approved_item` | ⛔ Q4 |

**D. Report**

| Test | Gate |
|---|---|
| Extend `test_page_numbers_match_the_text_output` (L138-173) with a capture and a cited bare drop | ✅ |
| `test_page_shows_a_distilled_capture` (Exit 4 analogue, with and without git) | ✅ (labels ⛔ Q4) |

**E. Regression.** The 80 existing tests stay green and unchanged.

## 5. Sequencing

| Phase | Work | Waits on |
|---|---|---|
| **0 — now** | W1.1-1.2, W2.1-2.3, W3.1-3.2, W3.7 link, W4.1-4.6, W4.9, W5.1/5.4, W7, W8.1/8.3, W9.3/9.6, every ✅ test | nothing |
| **1 — what producers write** | rest of W1 and W2, the `node:` part of W4.5, contract tests | Q1, Q3, Q5, Q8, Q9, Q11, Q12, Q13, Q14, Q15, Q16 |
| **2 — what Itakua derives and shows** | W4.7-4.8, W5.2-5.3, W3.3-3.6, W3.8-3.9, status tests | Q2, Q4, Q6, Q7 |
| **3 — process and release** | W3.4 final text, W8.2, W9.1-9.2, owner-run exits | Q10, Q17, Q18, Q19 |

Phase 1 and phase 2 barely overlap: Q2, Q4, Q6 and Q7 change nothing a producer writes. That
makes a split possible, and the choice belongs to the owner:

- **One PR.** One bump and one review. XFE-196 and XFE-189 wait for the phase 2 answers too.
- **Two PRs:** (1) spec, fixtures, the capture warning and the Captures subsection; (2) derived
  status, the page and the distil-flow edits. Producers are unblocked after phase 1. Costs two
  releases, and in between the skill names `captured_from:` before the validator reads it.

## 6. Exit and To-check

| Item | How it is verified | Who | Waits on |
|---|---|---|---|
| Exit 1a: spec merged with four fixtures | Review plus §4-A | Engineer, owner reviews | Phase 1 |
| Exit 1b: IR-041 and IA-039 reference the spec | Linear edits W9.1-9.2 | Owner / PM | Phase 1 |
| Exit 2: one real Dictalo class distils through the map flow into a thin log entry with provenance and a proposed `notes/` change | Owner-run session on the updated plugin | Owner | Q17 (today's Dictalo export is a bare drop), Q2, Q10, Q18 |
| Exit 3: a malformed capture warns; a bare drop is silent | §4-B | Tests | Q16 for the edge cases |
| Exit 4: after distilling, the page shows it distilled and the inbox file is untouched | §4-C/D, then the owner runs `--report` on the real brain | Tests, then owner | Q2, Q4, Q7. Whether the Learning brain is in git (which decides how inbox ages are read) is part of Q17 |
| To-check 1: a Web Clipper template emits a valid `kind: web` capture | One owner clip; optionally keep its output as a test input | Owner | Q11, Q12 (investigation, not a gate) |
| To-check 2: same-slug suffix across iCloud and Syncthing | Owner experiment once a producer exists | Owner | none (investigation) |
| To-check 3: parser reuse | W4.1 | Engineer | answered in W4.1 |

## 7. Risks

- **Decisions 1–4 are "proposed".** Record the owner's confirmation before the spec merges
  (W9.6).
- **The stale diagram is the most visual source.** Producers may copy its keys. Mark it
  superseded early (W9.3).
- **Test text format.** Six existing assertions match the inbox note line (W4.8). Reshaping that
  line breaks them, and it breaks the page/text agreement test too.
- **The validator now opens outsiders' files.** A crash hides every other finding. Guard every
  new read. The `validate()` helper already fails on any stderr.
- **Old installs.** Agents on 0.6.0 know nothing of captures until the plugin is updated and the
  session restarted.
