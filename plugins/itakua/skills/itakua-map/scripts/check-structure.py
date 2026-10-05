#!/usr/bin/env python3
"""Validate a brain against the four-slot framework, and against its own bindings.

    python3 <itakua-map>/scripts/check-structure.py          # structure + git state
    python3 <itakua-map>/scripts/check-structure.py --no-git # structure only, no git calls

A folder is either a SLOT (notes/ log/ docs/ inbox/) directly inside a node, something
filed INSIDE a slot, or a CHILD NODE (it has its own README.md). Any other folder inside a
node is LIMBO: the owner's, reported as a note and never a failure. A leftover _tmp/ is the
slot inbox/ replaced in 0.5.0, reported as legacy. A folder under spaces/ whose parent is
not a node is still a problem: that is a node missing its README.

A node whose docs/drive is linked declares where that folder lives in Drive with an
`artifacts:` key in its README frontmatter. Readers that cannot follow the symlink -- the
Reader, an agent on the MCP server -- have nothing else to go on. A missing, stale or
orphaned key is a WARNING: the key is optional, and a fresh clone has it before the link.

The git section exists because the structure was never the part that could hurt you.
A brain declares bindings in its root README -- remote, identity -- and those are the
things whose failure is silent and unrecoverable. Structure problems are a tidy-up;
a work brain pushed to a personal account is not. Git also says what the tree cannot:
which files exist only on this machine, which tracked files are large enough to weigh on
history for good, and whether the .gitignore keeps binaries out of inbox/. --no-git
skips every one of those queries.
"""
import os, sys, json, pathlib, re, subprocess, unicodedata, datetime

SLOTS = ("notes", "log", "docs", "inbox")
LEGACY = "_tmp"                  # the slot inbox/ replaced in 0.5.0
REQUIRED = ("notes", "log")
LARGE = 1024 * 1024              # a tracked file in a slot above this gets a warning
problems, warns, notes = [], [], []
# Every directory under spaces/, NFC-keyed: container, node, slot, inslot, limbo, legacy
# or orphan. Kept after the walk so later checks can tell slot content from limbo.
status = {}


# --- structure -------------------------------------------------------------------

def scan(root):
    """Classify every directory under spaces/, top-down.

    A slot is only a slot when its PARENT is a node. Matching the bare name anywhere
    in the path fails open: a node legitimately called `notes` or `log`, or anything
    beneath it, would be skipped by validation entirely.
    """
    found = []
    limbo_top = {}
    status[nfc(str(root))] = "container"
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        if dirpath == str(root):
            continue
        key, parent = nfc(dirpath), nfc(os.path.dirname(dirpath))
        base = os.path.basename(dirpath)
        pstat = status.get(parent, "container")
        rel = os.path.relpath(dirpath, ".")

        if pstat in ("slot", "inslot"):
            status[key] = "inslot"
        elif pstat in ("orphan", "legacy"):
            status[key] = pstat                   # already reported at the top
        elif pstat == "limbo":
            status[key] = "limbo"
            limbo_top[key] = top = limbo_top[parent]
            if "README.md" in filenames:
                warns.append(f"{rel}/ has a README.md but sits inside limbo {top}/, so it "
                             f"is not validated as a node -- every folder above a node "
                             f"must be a node too")
        elif base in SLOTS and pstat == "node":
            status[key] = "slot"
        elif base == LEGACY and pstat == "node":
            status[key] = "legacy"
            notes.append(f"{rel}/ is a legacy _tmp/ -- not a slot since 0.5.0 and still "
                         f"gitignored; move what should be filed into inbox/ by hand")
        elif "README.md" in filenames:
            status[key] = "node"
            found.append(pathlib.Path(dirpath))
        elif pstat == "node":
            status[key] = "limbo"
            limbo_top[key] = rel
            notes.append(f"{rel}/ is limbo (neither a slot nor a child node) -- the "
                         f"owner's; agents leave it alone")
        else:
            status[key] = "orphan"
            if base in SLOTS:
                problems.append(f"{rel}/ is named like a slot but its parent is not a "
                                f"node -- give the parent a README.md, or rename this")
            else:
                problems.append(f"{rel}/ is neither a slot nor a node (no README.md) -- "
                                f"give it a README.md, or move it inside a node")
    return found


def check_nodes(found):
    for n in found:
        readme = (n / "README.md").read_text(encoding="utf-8")
        for s in REQUIRED:
            if not (n / s).is_dir():
                problems.append(f"{n}/ is missing required slot {s}/")
        for s in SLOTS:
            if (n / s).is_dir() and f"`{s}/`" not in readme:
                problems.append(f"{n}/README.md does not list {s}/, which exists")
            if not (n / s).is_dir() and f"`{s}/`" in readme \
                    and "*Unused" not in readme and "*Optional" not in readme:
                notes.append(f"{n}/README.md mentions {s}/, which does not exist")


# --- inbox -----------------------------------------------------------------------

def inbox_items(inbox):
    """Every file captured in an inbox, at any depth. Dotfiles (.gitkeep) are not items."""
    items = []
    for dirpath, dirnames, filenames in os.walk(inbox):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        items += [pathlib.Path(dirpath, f) for f in sorted(filenames)
                  if not f.startswith(".")]
    return items


def first_added(found):
    """When git first saw each inbox file, by path: one `git log` over every inbox.

    A clone or checkout resets mtime, so on a fresh clone every tracked item would look
    like it arrived today. The commit that added it does not move.
    """
    inboxes = [str(n / "inbox") for n in found if (n / "inbox").is_dir()]
    out = git_raw("log", "--diff-filter=A", "--relative", "-z", "--name-only",
                  "--format=%x01%ct", "--", *inboxes) if inboxes else None
    added, when = {}, None
    for token in (out or "").split("\0"):
        token = token.lstrip("\n")
        if token.startswith("\x01"):
            when = int(token[1:])
        elif token and when is not None:
            added.setdefault(nfc(token), when)    # newest first: the current file's add
    return added


def check_inbox(found, added):
    """One note per node with something in its inbox: how many, and since when."""
    today = datetime.date.today()
    for n in found:
        inbox = n / "inbox"
        if not inbox.is_dir():
            continue
        items = inbox_items(inbox)
        if not items:
            continue
        stamps = []
        for item in items:
            times = [added[k] for k in (nfc(item.as_posix()),) if k in added]
            try:
                times.append(item.lstat().st_mtime)
            except OSError:
                pass
            if times:
                stamps.append(min(times))
        oldest = datetime.date.fromtimestamp(min(stamps)) if stamps else None
        age = (f", oldest {oldest.isoformat()} ({(today - oldest).days} day(s))"
               if oldest else "")
        notes.append(f"{inbox}/: {len(items)} item(s){age}")


# --- what git says about the tree --------------------------------------------------

def node_of(path):
    """The nearest node at or above `path`, or None when it is not inside one."""
    d = nfc(path)
    while d and d != ".":
        if status.get(d) == "node":
            return d
        d = os.path.dirname(d)
    return None


def check_local_only():
    """Files under spaces/ that git ignores: they exist on this machine and nowhere else.

    docs/drive is excluded (the cloud holds it), and so are dotfiles and legacy _tmp/,
    which is already reported as a whole.
    """
    out = git_raw("ls-files", "-z", "-o", "-i", "--exclude-standard", "--", "spaces")
    by_node = {}
    for path in (out or "").split("\0"):
        folder = os.path.dirname(path)
        if not path or any(part.startswith(".") for part in path.split("/")):
            continue
        if status.get(nfc(folder)) == "legacy":
            continue
        if path.endswith("/docs/drive") and status.get(nfc(folder)) == "slot":
            continue                              # the symlink itself; git never follows it
        by_node.setdefault(node_of(folder), []).append(path)
    for node, paths in sorted(by_node.items(), key=lambda kv: kv[0] or ""):
        shown = [os.path.relpath(p, node) if node else p for p in paths]
        more = f", and {len(shown) - 5} more" if len(shown) > 5 else ""
        notes.append(f"{node or 'spaces'}/: {len(paths)} file(s) only on this machine "
                     f"(ignored by git, outside docs/drive): {', '.join(shown[:5])}{more}")


def check_sizes():
    """Tracked files in a slot above LARGE: git history keeps them for good."""
    out = git_raw("ls-files", "-z", "--", "spaces")
    for path in (out or "").split("\0"):
        if not path or status.get(nfc(os.path.dirname(path))) not in ("slot", "inslot"):
            continue
        try:
            size = os.lstat(path).st_size
        except OSError:
            continue
        if size > LARGE:
            warns.append(f"{path} is {size / LARGE:.1f} MB and tracked by git -- history "
                         f"keeps every version; move it to docs/drive unless it must be "
                         f"versioned")


def check_allowlist(found):
    """Ask git whether a binary dropped in a real inbox would be ignored."""
    inboxes = [n / "inbox" for n in found if (n / "inbox").is_dir()]
    if not inboxes:
        return
    probe = (inboxes[0] / "capture.heic").as_posix()
    if git("check-ignore", "-q", "--no-index", probe) is None:
        warns.append(f".gitignore would commit binaries dropped in inbox/ ({probe} is not "
                     f"ignored) -- add the inbox allowlist the itakua-map skill gives, so "
                     f"only text is tracked there")


# --- artifact layer ---------------------------------------------------------------

def indexed_artifact_count(index):
    """Return an index's artifact count, or None when it cannot be read reliably."""
    try:
        text = index.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    # Generated indexes carry the count in their English or Spanish summary line.
    match = re.search(r"(?m)^(\d+)\s+(?:files?|archivos?)\s+·", text)
    return int(match.group(1)) if match else None


def index_claim(index):
    """Describe what an index claims without making its prose a rigid schema."""
    count = indexed_artifact_count(index)
    return (f"{index} has no readable artifact count" if count is None
            else f"{index} records {count} artifact(s)")


def check_artifacts(found):
    """Check each node's direct docs/drive edge without assuming docs is in use."""
    for n in found:
        docs = n / "docs"
        index = docs / "index.md"
        drive = docs / "drive"
        has_index = os.path.lexists(str(index))

        if drive.is_symlink():
            if not drive.exists():
                detail = f"; {index_claim(index)}" if has_index else ""
                problems.append(
                    f"{drive} is a dangling or unavailable symlink{detail} -- "
                    "load itakua-setup to repair the local attachment"
                )
            elif not drive.is_dir():
                problems.append(f"{drive} is a symlink but does not point to a directory")
        elif os.path.lexists(str(drive)):
            problems.append(f"{drive} exists but is not a symlink")
        elif has_index:
            count = indexed_artifact_count(index)
            if count is None:
                problems.append(
                    f"{drive} is absent and {index} has no readable artifact count -- "
                    "load itakua-setup to repair the local attachment"
                )
            elif count > 0:
                problems.append(
                    f"{drive} is absent but {index} records {count} artifact(s) -- "
                    "load itakua-setup to repair the local attachment"
                )
            else:
                notes.append(f"{index} records 0 artifacts; {drive} is absent")
        elif docs.is_dir():
            notes.append(f"{n}/ has an unused docs/ slot (no index or drive link)")


# --- artifact store declaration ---------------------------------------------------

PROVIDERS = ("google-drive",)
# The top-level folders of a Google Drive mirror, as Drive names them. A machine path is
# turned into a Drive root only from one of these; anything else is not proposed.
DRIVE_ANCHORS = ("My Drive", "Shared drives")
# Characters YAML will not take raw in a plain or single-quoted scalar, plus surrogates.
UNPRINTABLE = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff]")


def nfc(text):
    # macOS hands back decomposed file names; a README is usually typed composed.
    return unicodedata.normalize("NFC", text)


def frontmatter(text):
    """The lines of a leading `---` frontmatter block, or [] when there is none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return lines[1:i]
    return []


def scalar(value):
    """A YAML scalar as the block form writes it: quotes undone, trailing comment dropped.

    None for a value YAML would read differently from how it looks -- an unquoted `: `
    or trailing `:` -- so the caller reports it instead of agreeing with a wrong value.
    """
    value = value.strip(" \t")                     # YAML whitespace, not Unicode's
    if value.startswith("'"):
        m = re.fullmatch(r"'((?:[^']|'')*)'(?:[ \t]+#.*)?", value)
        value = m.group(1).replace("''", "'") if m else None
    elif value.startswith('"'):
        m = re.fullmatch(r'"((?:[^"\\]|\\.)*)"(?:[ \t]+#.*)?', value)
        try:
            value = json.loads(f'"{m.group(1)}"') if m else None
        except ValueError:
            value = None
        # Escapes may carry control characters, which YAML allows here; a lone
        # surrogate is not text at all and would crash the warning that prints it.
        return None if value is None or re.search("[\ud800-\udfff]", value) else value
    elif value.startswith("#"):
        return ""
    else:
        value = re.split(r"[ \t]+#", value, maxsplit=1)[0].strip(" \t")
        if re.search(r":([ \t]|$)", value):
            return None
    return None if value is None or UNPRINTABLE.search(value) else value


def yaml_scalar(value):
    """`value` written so that YAML and scalar() both read it back unchanged."""
    if UNPRINTABLE.search(value):
        # Only a double-quoted scalar can carry these, and only as escapes.
        return '"' + re.sub(r'[\x00-\x1f\x7f-\x9f\u2028\u2029"\\]',
                            lambda m: f"\\u{ord(m.group()):04x}", value) + '"'
    if re.search(r""":(\s|$)|\s#|^\s|\s$|^[-?:,\[\]{}#&*!|>'"%@`]""", value):
        return "'" + value.replace("'", "''") + "'"
    return value


def declared_artifacts(text):
    """The README's `artifacts:` fields as a dict, or None when the key is absent.

    Not a YAML parser, on purpose: frontmatter stays flat apart from this one two-field
    block, and the validator has to run on a bare python3. A form it cannot read comes
    back without `root`, which is reported rather than guessed at.
    """
    lines = frontmatter(text)
    for i, line in enumerate(lines):
        m = re.match(r"artifacts:(.*)$", line)
        if not m:
            continue
        fields = {}
        if scalar(m.group(1)) != "":
            return fields                          # inline or flow form
        for sub in lines[i + 1:]:
            if not sub.strip() or sub.lstrip().startswith("#"):
                continue
            if not sub[:1].isspace():
                break
            if "\t" in sub[:len(sub) - len(sub.lstrip())]:
                return {}                          # YAML forbids tab indentation
            field = re.match(r"\s+([A-Za-z_]+):(.*)$", sub)
            if field:
                fields[field.group(1)] = scalar(field.group(2))
        return fields
    return None


def drive_root_of(target):
    """'/Users/x/.../GoogleDrive-x/My Drive/Guitarra' -> 'My Drive/Guitarra', else None."""
    parts = [nfc(p) for p in re.split(r"[\\/]+", target) if p]
    for i, part in enumerate(parts):
        if part in DRIVE_ANCHORS:
            return "/".join(parts[i:])
    return None


def local_map_target(node_key):
    """The node's `.drive-map.local` target, read the way link-drive.sh reads it."""
    path = pathlib.Path(".drive-map.local")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    for line in text.splitlines():
        if re.match(r"\s*#", line):
            continue
        fields = line.split("|")
        if len(fields) >= 2 and fields[0] == node_key:
            return fields[1] or None
    return None


def mapped_root(node, drive):
    """Where this machine's mapping puts the node's artifacts in Drive.

    Returns (root, source), or (None, None) when the mapping does not reach a Drive
    folder. `.drive-map.local` wins, as it does for link-drive.sh; otherwise the
    symlink's own target, which is what the committed `drive-map` resolved to here.
    """
    target = local_map_target(node.relative_to("spaces").as_posix())
    if target and drive_root_of(target):
        return drive_root_of(target), ".drive-map.local"
    if drive.is_symlink():
        link = os.path.normpath(os.path.join(str(drive.parent), os.readlink(str(drive))))
        if drive_root_of(link):
            return drive_root_of(link), f"the target of {drive}"
    return None, None


def check_artifact_store(found):
    """Compare each README's `artifacts:` key with the node's docs/drive link."""
    for n in found:
        readme = n / "README.md"
        declared = declared_artifacts(readme.read_text(encoding="utf-8"))
        drive = n / "docs" / "drive"
        root, source = mapped_root(n, drive)

        if declared is None:
            if drive.is_symlink():
                proposal = (f"; from {source}, propose `provider: google-drive` and "
                            f"`root: {yaml_scalar(root)}`" if root else
                            "; set `root` to the Drive folder docs/drive points to, as "
                            "Drive shows it")
                warns.append(f"{n}/ has docs/drive but {readme} declares no `artifacts:` "
                             f"key{proposal}. Adding it is a README edit: owner approval")
            continue

        declared_root = nfc(declared.get("root") or "").strip("/")
        provider = declared.get("provider") or ""
        if not declared_root:
            warns.append(f"{readme} has an `artifacts:` key with no readable `root` -- "
                         f"use the two-line block form the itakua-map skill defines, "
                         f"indented with spaces, quoting a value with `: ` or ` #` in it")
        elif "<" in declared_root or ">" in declared_root:
            warns.append(f"{readme} `artifacts.root` is still a placeholder: {declared_root}")
            declared_root = ""
        if provider not in PROVIDERS:
            warns.append(f"{readme} `artifacts.provider` is {provider or 'missing'}; the "
                         f"framework defines {', '.join(PROVIDERS)}")

        if not os.path.lexists(str(drive)):
            warns.append(f"{readme} declares `artifacts:` but {drive} is not linked on this "
                         f"machine -- load itakua-setup to attach it, or drop the key if "
                         f"the node keeps no artifacts in Drive")
        elif root and declared_root and declared_root != root:
            warns.append(f"{readme} declares `artifacts.root: {declared_root}`, but {source} "
                         f"gives `root: {yaml_scalar(root)}` -- correct whichever is stale, "
                         f"with owner approval")


# --- git state -------------------------------------------------------------------

def git_raw(*args):
    """git's stdout as is, or None when git fails or is missing."""
    try:
        r = subprocess.run(("git",) + args, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def git(*args):
    out = git_raw(*args)
    return out.strip() if out is not None else None


def declared_bindings():
    """Read the bindings table out of the root README, if there is one.

    The table is the brain's own statement of what it expects. Nothing else on disk
    knows whether a remote is a mistake or the plan.
    """
    out = {}
    readme = pathlib.Path("README.md")
    if not readme.is_file():
        return out
    for line in readme.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        # Only the first two columns are read. A brain is free to add its own -- a
        # constraint/preference marker, a note -- without the table stopping being
        # machine-readable.
        key = cells[0].replace("*", "").strip().lower()
        if key in ("git remote", "git identity", "path"):
            out[key] = cells[1]
    return out


def check_git():
    if git("rev-parse", "--git-dir") is None:
        notes.append("not a git repository -- git bindings not checked")
        return

    declared = declared_bindings()
    remotes = [r for r in (git("remote") or "").splitlines() if r.strip()]
    local_name = git("config", "--local", "user.name")
    local_mail = git("config", "--local", "user.email")
    global_mail = git("config", "--global", "user.email")

    # --- remote ---
    decl_remote = declared.get("git remote", "")
    if remotes:
        urls = ", ".join(f"{r} -> {git('remote', 'get-url', r) or '?'}" for r in remotes)
        if re.search(r"\bnone\b", decl_remote, re.I) and "none yet" not in decl_remote.lower():
            problems.append(
                f"README declares NO REMOTE, and {len(remotes)} is configured: {urls} "
                f"-- if this brain holds material that must not be published, this is "
                f"the failure the declaration exists to prevent")
        else:
            notes.append(f"remote(s): {urls}")
    else:
        notes.append("no remote configured")

    # --- identity ---
    if not local_mail:
        if global_mail:
            problems.append(
                f"no repository-local git identity -- commits here will be authored as "
                f"the GLOBAL identity <{global_mail}>. Set one: "
                f"git config --local user.email you@example.com; load itakua-setup to "
                f"repair the machine-local binding")
        else:
            problems.append(
                "no git identity, local or global -- commits will fail or be authored "
                "by a guess. Load itakua-setup and set a local one"
            )
    else:
        if global_mail and global_mail == local_mail:
            notes.append(f"local identity <{local_mail}> is the same as the global one")
        m = re.search(r"([^<>|*]+?)\s*<([^<>@\s]+@[^<>@\s]+)>", declared.get("git identity", ""))
        if m:
            want_name, want_mail = m.group(1).strip(), m.group(2).strip()
            if want_mail != local_mail:
                problems.append(f"README declares identity <{want_mail}>, repository is "
                                f"configured as <{local_mail}> -- load itakua-setup to "
                                f"repair the machine-local binding")
            elif want_name != (local_name or ""):
                notes.append(f"README declares name '{want_name}', repository has "
                             f"'{local_name}' -- load itakua-setup if the declared "
                             f"identity should be restored")
            else:
                notes.append(f"identity matches the README: {local_name} <{local_mail}>")
        else:
            notes.append(f"identity: {local_name} <{local_mail}> (README declares none)")

    # --- the spine exists at all ---
    for f in ("README.md", ".gitignore"):
        if not pathlib.Path(f).is_file():
            notes.append(f"no {f} at the repository root")


# --- main ------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    for a in args:
        if a not in ("--git", "--no-git"):
            sys.exit(f"usage: check-structure.py [--no-git]\nunknown option {a}")

    root = pathlib.Path("spaces")
    if not root.is_dir():
        sys.exit("no spaces/ -- run from the repo root. Every brain has spaces/ at its "
                 "root; it is where all content lives")

    if pathlib.Path("areas").exists():
        problems.append("legacy areas/ exists beside spaces/ -- new Itakua brains use only "
                        "spaces/. Do not migrate an existing brain without owner approval")

    in_git = "--no-git" not in args and git("rev-parse", "--git-dir") is not None
    found = scan(root)
    check_nodes(found)
    check_inbox(found, first_added(found) if in_git else {})
    check_artifacts(found)
    check_artifact_store(found)
    if in_git:
        check_local_only()
        check_sizes()
        check_allowlist(found)
    if "--no-git" not in args:
        check_git()

    print(f"{len(found)} nodes checked: " + ", ".join(str(n) for n in sorted(found)))
    for m in notes:
        print(f"  note     {m}")
    for m in warns:
        print(f"  WARN     {m}")
    for m in problems:
        print(f"  PROBLEM  {m}")
    tail = f" {len(warns)} warning(s)." if warns else ""
    print("\nOK -- structure and bindings are consistent." + tail if not problems
          else f"\n{len(problems)} problem(s).{tail}")
    return 1 if problems else 0


sys.exit(main())
