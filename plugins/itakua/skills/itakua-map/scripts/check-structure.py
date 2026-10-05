#!/usr/bin/env python3
"""Validate a brain against the four-slot framework, and against its own bindings.

    python3 <itakua-map>/scripts/check-structure.py          # structure + git state
    python3 <itakua-map>/scripts/check-structure.py --no-git # structure only, no git calls
    python3 <itakua-map>/scripts/check-structure.py --report # also write status.html

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
skips every one of those queries. A query that fails or times out is a WARN, and what it
would have counted is "not checked" -- never zero, which would be an all-clear.

--report writes status.html at the brain root once the checks finish: the same findings,
plus each node's inbox, undistilled log entries, limbo and machine-local files, as one
static page from assets/status-page.html. Without it the validator writes nothing.
"""
import os, sys, json, pathlib, re, subprocess, unicodedata, datetime, html, platform
import string

SLOTS = ("notes", "log", "docs", "inbox")
LEGACY = "_tmp"                  # the slot inbox/ replaced in 0.5.0
REQUIRED = ("notes", "log")
ROOT_INBOX = "00-inbox"
LARGE = 1024 * 1024              # a tracked file in a slot above this gets a warning
REPORT = "status.html"
GIT_TIMEOUT = 10                 # seconds; a slower query is reported, never read as empty
TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "assets" / "status-page.html"

# Findings, each as (node, message): node is the NFC path of the node it is about, or None
# for the brain as a whole. The text output and the status page both read these lists.
problems, warns, notes = [], [], []
# What the status page shows beside the findings, by node (None is the brain). Filled by
# the same checks that print, so every number on the page is one the text output gave.
facts = {}
# Every directory under spaces/, NFC-keyed: container, node, slot, inslot, limbo, legacy
# or orphan. Kept after the walk so later checks can tell slot content from limbo.
status = {}
# What a failed git query left unknown ("local", "ages"): shown as not checked, never 0.
unchecked = set()


def problem(msg, node=None):
    problems.append((node, msg))


def warn(msg, node=None):
    warns.append((node, msg))


def note(msg, node=None):
    notes.append((node, msg))


def key(node):
    """How a node is named in findings and facts: its path, NFC, as a string."""
    return nfc(str(node))


def fact(node):
    return facts.setdefault(node, {})


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
        here, parent = nfc(dirpath), nfc(os.path.dirname(dirpath))
        base = os.path.basename(dirpath)
        pstat = status.get(parent, "container")
        rel = os.path.relpath(dirpath, ".")

        if pstat in ("slot", "inslot"):
            status[here] = "inslot"
        elif pstat in ("orphan", "legacy"):
            status[here] = pstat                  # already reported at the top
        elif pstat == "limbo":
            status[here] = "limbo"
            limbo_top[here] = top = limbo_top[parent]
            if "README.md" in filenames:
                warn(f"{rel}/ has a README.md but sits inside limbo {top}/, so it is not "
                     f"validated as a node -- every folder above a node must be a node "
                     f"too", node=node_of(parent))
        elif base in SLOTS and pstat == "node":
            status[here] = "slot"
        elif base == LEGACY and pstat == "node":
            status[here] = "legacy"
            fact(parent)["legacy"] = rel
            note(f"{rel}/ is a legacy _tmp/ -- not a slot since 0.5.0 and still "
                 f"gitignored; move what should be filed into inbox/ by hand", node=parent)
        elif "README.md" in filenames:
            status[here] = "node"
            found.append(pathlib.Path(dirpath))
        elif pstat == "node":
            status[here] = "limbo"
            limbo_top[here] = rel
            fact(parent).setdefault("limbo", []).append(rel)
            note(f"{rel}/ is limbo (neither a slot nor a child node) -- the owner's; "
                 f"agents leave it alone", node=parent)
        else:
            status[here] = "orphan"
            if base in SLOTS:
                problem(f"{rel}/ is named like a slot but its parent is not a node -- "
                        f"give the parent a README.md, or rename this")
            else:
                problem(f"{rel}/ is neither a slot nor a node (no README.md) -- give it "
                        f"a README.md, or move it inside a node")
    return found


def check_nodes(found):
    for n in found:
        readme = (n / "README.md").read_text(encoding="utf-8")
        for s in REQUIRED:
            if not (n / s).is_dir():
                problem(f"{n}/ is missing required slot {s}/", node=key(n))
        for s in SLOTS:
            if (n / s).is_dir() and f"`{s}/`" not in readme:
                problem(f"{n}/README.md does not list {s}/, which exists", node=key(n))
            if not (n / s).is_dir() and f"`{s}/`" in readme \
                    and "*Unused" not in readme and "*Optional" not in readme:
                note(f"{n}/README.md mentions {s}/, which does not exist", node=key(n))


# --- inbox and log -----------------------------------------------------------------

def inboxes(found):
    """Every inbox to report on, as (node, path): each node's inbox/, then 00-inbox/."""
    pairs = [(key(n), n / "inbox") for n in found if (n / "inbox").is_dir()]
    if pathlib.Path(ROOT_INBOX).is_dir():
        pairs.append((None, pathlib.Path(ROOT_INBOX)))
    return pairs


def inbox_items(inbox):
    """Every file captured in an inbox, at any depth. Dotfiles (.gitkeep) are not items."""
    items = []
    for dirpath, dirnames, filenames in os.walk(inbox):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        items += [pathlib.Path(dirpath, f) for f in sorted(filenames)
                  if not f.startswith(".")]
    return items


def first_added(pairs):
    """When git first saw each inbox file, by path: one `git log` over every inbox.

    A clone or checkout resets ctime, so on a fresh clone every tracked item would look
    like it arrived today. The commit that added it does not move. None when the history
    could not be read.
    """
    paths = [str(path) for _, path in pairs]
    if not paths:
        return {}
    out = git_query("Inbox ages", "log", "--diff-filter=A", "--relative", "-z",
                    "--name-only", "--format=%x01%ct", "--", *paths)
    if out is None:
        unchecked.add("ages")
        return None
    added, when = {}, None
    for token in out.split("\0"):
        token = token.lstrip("\n")
        if token.startswith("\x01"):
            when = int(token[1:])
        elif token and when is not None:
            added.setdefault(nfc(token), when)    # newest first: the current file's add
    return added


def check_inbox(pairs, added):
    """One note per inbox with something in it: how many, and since when.

    An item has waited since it arrived: the earlier of its ctime, which a move, copy,
    download or checkout sets, and the commit that added it. Never mtime: a 2019 PDF
    dropped in today has not waited since 2019. ctime also moves on any metadata change
    (an edit, a chmod, an app tagging the file it opens), so an untracked item can look
    newer than it is, never older. With `added` None the history was unreadable, and
    ages are not checked rather than guessed from a ctime a checkout may have reset.
    """
    today = datetime.date.today()
    for node, inbox in pairs:
        items = inbox_items(inbox)
        stamps = []
        for item in items if added is not None else ():
            times = [added[k] for k in (nfc(item.as_posix()),) if k in added]
            try:
                times.append(item.lstat().st_ctime)
            except OSError:
                pass
            if times:
                stamps.append(min(times))
        oldest = datetime.date.fromtimestamp(min(stamps)) if stamps else None
        days = (today - oldest).days if oldest else None
        fact(node)["inbox"] = {"count": len(items), "oldest": oldest, "days": days}
        if items:
            age = (", oldest not checked" if added is None else
                   f", oldest {oldest.isoformat()} ({days} day(s))" if oldest else "")
            note(f"{inbox}/: {len(items)} item(s){age}", node=node)


def check_distilled(found):
    """Log entries nobody has looked at yet: no `distilled_into` anywhere in the file.

    The same audit as `grep -rL --include='*.md' distilled_into log/`. `distilled_into: []`
    means considered, nothing to lift, so only a missing field counts.
    """
    for n in found:
        log = n / "log"
        if not log.is_dir():
            continue
        pending = 0
        for dirpath, dirnames, filenames in os.walk(log):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for f in filenames:
                if f.startswith(".") or not f.endswith(".md"):
                    continue
                try:
                    text = pathlib.Path(dirpath, f).read_text(encoding="utf-8",
                                                              errors="replace")
                except OSError:
                    continue
                pending += "distilled_into" not in text
        fact(key(n))["undistilled"] = pending
        if pending:
            note(f"{log}/: {pending} entr{'y' if pending == 1 else 'ies'} with no "
                 f"distilled_into -- nobody has looked yet", node=key(n))


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
    """Files git ignores under spaces/ and 00-inbox/: they exist on this machine only.

    docs/drive is excluded (the cloud holds it), and so are dotfiles and legacy _tmp/,
    which is already reported as a whole.
    """
    out = git_query("Files only on this machine", "ls-files", "-z", "-o", "-i",
                    "--exclude-standard", "--", "spaces", ROOT_INBOX)
    if out is None:
        unchecked.add("local")
        return
    by_node = {}
    for path in out.split("\0"):
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
        fact(node)["local_only"] = shown
        more = f", and {len(shown) - 5} more" if len(shown) > 5 else ""
        where = f"{node}/: {len(paths)} file(s)" if node else \
            f"{len(paths)} file(s) outside any node"
        note(f"{where} only on this machine (ignored by git, outside docs/drive): "
             f"{', '.join(shown[:5])}{more}", node=node)


def check_sizes():
    """Tracked files in a slot above LARGE: git history keeps them for good."""
    out = git_query("Tracked files over 1 MB", "ls-files", "-z", "--", "spaces")
    for path in (out or "").split("\0"):           # None: already warned
        if not path or status.get(nfc(os.path.dirname(path))) not in ("slot", "inslot"):
            continue
        try:
            size = os.lstat(path).st_size
        except OSError:
            continue
        if size > LARGE:
            warn(f"{path} is {size / LARGE:.1f} MB and tracked by git -- history keeps "
                 f"every version; move it to docs/drive unless it must be versioned",
                 node=node_of(os.path.dirname(path)))


def check_allowlist(found):
    """Ask git whether a binary dropped in a real inbox, or in 00-inbox/, is ignored."""
    probes = [n / "inbox" for n in found if (n / "inbox").is_dir()][:1]
    if pathlib.Path(ROOT_INBOX).is_dir():
        probes.append(pathlib.Path(ROOT_INBOX))
    for inbox in probes:
        probe = (inbox / "capture.heic").as_posix()
        if git_ignores(f"The {inbox.name}/ allowlist", probe, "--no-index") is False:
            warn(f".gitignore would commit binaries dropped in {inbox.name}/ ({probe} is "
                 f"not ignored) -- add the inbox allowlist the itakua-map skill gives, so "
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
        at = key(n)

        if drive.is_symlink():
            if not drive.exists():
                fact(at)["drive"] = "dangling"
                detail = f"; {index_claim(index)}" if has_index else ""
                problem(f"{drive} is a dangling or unavailable symlink{detail} -- "
                        "load itakua-setup to repair the local attachment", node=at)
            elif not drive.is_dir():
                fact(at)["drive"] = "not a directory"
                problem(f"{drive} is a symlink but does not point to a directory", node=at)
            else:
                fact(at)["drive"] = "linked"
        elif os.path.lexists(str(drive)):
            fact(at)["drive"] = "not a symlink"
            problem(f"{drive} exists but is not a symlink", node=at)
        elif has_index:
            fact(at)["drive"] = "absent"
            count = indexed_artifact_count(index)
            if count is None:
                problem(f"{drive} is absent and {index} has no readable artifact count -- "
                        "load itakua-setup to repair the local attachment", node=at)
            elif count > 0:
                problem(f"{drive} is absent but {index} records {count} artifact(s) -- "
                        "load itakua-setup to repair the local attachment", node=at)
            else:
                note(f"{index} records 0 artifacts; {drive} is absent", node=at)
        elif docs.is_dir():
            fact(at)["drive"] = "unused docs/"
            note(f"{n}/ has an unused docs/ slot (no index or drive link)", node=at)


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
        at = key(n)
        if root:
            fact(at)["drive_root"] = root

        if declared is None:
            if drive.is_symlink():
                proposal = (f"; from {source}, propose `provider: google-drive` and "
                            f"`root: {yaml_scalar(root)}`" if root else
                            "; set `root` to the Drive folder docs/drive points to, as "
                            "Drive shows it")
                warn(f"{n}/ has docs/drive but {readme} declares no `artifacts:` "
                     f"key{proposal}. Adding it is a README edit: owner approval", node=at)
            continue

        declared_root = nfc(declared.get("root") or "").strip("/")
        provider = declared.get("provider") or ""
        fact(at)["artifacts"] = declared_root
        if not declared_root:
            warn(f"{readme} has an `artifacts:` key with no readable `root` -- use the "
                 f"two-line block form the itakua-map skill defines, indented with spaces, "
                 f"quoting a value with `: ` or ` #` in it", node=at)
        elif "<" in declared_root or ">" in declared_root:
            warn(f"{readme} `artifacts.root` is still a placeholder: {declared_root}",
                 node=at)
            declared_root = ""
        if provider not in PROVIDERS:
            warn(f"{readme} `artifacts.provider` is {provider or 'missing'}; the "
                 f"framework defines {', '.join(PROVIDERS)}", node=at)

        if not os.path.lexists(str(drive)):
            warn(f"{readme} declares `artifacts:` but {drive} is not linked on this "
                 f"machine -- load itakua-setup to attach it, or drop the key if the node "
                 f"keeps no artifacts in Drive", node=at)
        elif root and declared_root and declared_root != root:
            warn(f"{readme} declares `artifacts.root: {declared_root}`, but {source} "
                 f"gives `root: {yaml_scalar(root)}` -- correct whichever is stale, with "
                 f"owner approval", node=at)


# --- git state -------------------------------------------------------------------

def git_call(*args):
    """Run git: (result, None), or (None, reason) when it cannot run or times out."""
    try:
        return subprocess.run(("git",) + args, capture_output=True, text=True,
                              timeout=GIT_TIMEOUT), None
    except subprocess.TimeoutExpired:
        return None, f"timed out after {GIT_TIMEOUT} s"
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e) or type(e).__name__


def git_failed(what, args, result, reason):
    if result is not None:
        reason = (result.stderr.strip().splitlines() or
                  [f"exit status {result.returncode}"])[0]
    warn(f"{what} not checked: `git {args[0]}` failed ({reason}) -- run the validator "
         f"again")


def git_query(what, *args):
    """The stdout of a query a check depends on, or None after a WARN that says so.

    A failed query must never read as an empty answer. "0 files only on this machine"
    is an all-clear, and git timing out is not one.
    """
    result, reason = git_call(*args)
    if result is not None and result.returncode == 0:
        return result.stdout
    git_failed(what, args, result, reason)
    return None


def git_ignores(what, path, *flags):
    """Whether git ignores `path`: True or False, or None after a WARN when git fails."""
    args = ("check-ignore", "-q", *flags, path)
    result, reason = git_call(*args)
    if result is not None and result.returncode in (0, 1):
        return result.returncode == 0
    git_failed(what, args, result, reason)
    return None


def git_raw(*args):
    """git's stdout as is, or None when git fails. Only for lookups where failing means
    absent, like an unset config key; anything a check counts goes through git_query."""
    result, _ = git_call(*args)
    return result.stdout if result is not None and result.returncode == 0 else None


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
        fact(None)["git"] = "not a git repository"
        note("not a git repository -- git bindings not checked")
        return

    declared = declared_bindings()
    listed = git_query("Git remote", "remote")
    remotes = None if listed is None else [r for r in listed.splitlines() if r.strip()]
    local_name = git("config", "--local", "user.name")
    local_mail = git("config", "--local", "user.email")
    global_mail = git("config", "--global", "user.email")

    # --- remote ---
    decl_remote = declared.get("git remote", "")
    if remotes is None:
        fact(None)["remote"] = "not checked"     # the WARN says why
    elif remotes:
        urls = ", ".join(f"{r} -> {git('remote', 'get-url', r) or '?'}" for r in remotes)
        fact(None)["remote"] = urls
        if re.search(r"\bnone\b", decl_remote, re.I) and "none yet" not in decl_remote.lower():
            problem(
                f"README declares NO REMOTE, and {len(remotes)} is configured: {urls} "
                f"-- if this brain holds material that must not be published, this is "
                f"the failure the declaration exists to prevent")
        else:
            note(f"remote(s): {urls}")
    else:
        fact(None)["remote"] = "none"
        note("no remote configured")
    fact(None)["identity"] = (f"{local_name or '?'} <{local_mail}>" if local_mail else
                              f"not set here (global <{global_mail}>)" if global_mail else
                              "not set")

    # --- identity ---
    if not local_mail:
        if global_mail:
            problem(
                f"no repository-local git identity -- commits here will be authored as "
                f"the GLOBAL identity <{global_mail}>. Set one: "
                f"git config --local user.email you@example.com; load itakua-setup to "
                f"repair the machine-local binding")
        else:
            problem(
                "no git identity, local or global -- commits will fail or be authored "
                "by a guess. Load itakua-setup and set a local one"
            )
    else:
        if global_mail and global_mail == local_mail:
            note(f"local identity <{local_mail}> is the same as the global one")
        m = re.search(r"([^<>|*]+?)\s*<([^<>@\s]+@[^<>@\s]+)>", declared.get("git identity", ""))
        if m:
            want_name, want_mail = m.group(1).strip(), m.group(2).strip()
            if want_mail != local_mail:
                problem(f"README declares identity <{want_mail}>, repository is "
                        f"configured as <{local_mail}> -- load itakua-setup to "
                        f"repair the machine-local binding")
            elif want_name != (local_name or ""):
                note(f"README declares name '{want_name}', repository has "
                     f"'{local_name}' -- load itakua-setup if the declared "
                     f"identity should be restored")
            else:
                note(f"identity matches the README: {local_name} <{local_mail}>")
        else:
            note(f"identity: {local_name} <{local_mail}> (README declares none)")

    # --- the spine exists at all ---
    for f in ("README.md", ".gitignore"):
        if not pathlib.Path(f).is_file():
            note(f"no {f} at the repository root")


# --- status page -------------------------------------------------------------------

LEVELS = (("problem", "PROBLEM", problems), ("warn", "WARN", warns), ("note", "note", notes))


def esc(value):
    return html.escape(str(value), quote=True)


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def brain_name():
    """The root README's title, or the folder name when it has none."""
    try:
        for line in pathlib.Path("README.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except (OSError, UnicodeError):
        pass
    return pathlib.Path.cwd().name


def finding_li(cls, label, msg, at=None):
    where = f'<span class="at">{esc(at)}/</span> ' if at and not msg.startswith(at) else ""
    return (f'<li class="f-{cls}"><span class="tag">{label}</span>'
            f'<span>{where}{esc(msg)}</span></li>')


def attention_html():
    """Problems and warnings, one by one, above everything else: they need acting on."""
    rows = [finding_li(cls, label, msg, at)
            for cls, label, items in LEVELS[:2] for at, msg in items]
    if not rows:
        return ""
    return (f'<section class="panel attention"><h2>Needs attention</h2>'
            f'<ul class="findings">{"".join(rows)}</ul></section>')


def notes_html():
    """Notes, with the ones that differ only in their node folded into one line.

    Ten nodes with a legacy _tmp/ make ten notes that say the same thing; the page shows
    the sentence once and lists the nodes under it.
    """
    groups = {}
    for at, msg in notes:
        shape = msg.replace(at, "\0", 1) if at and msg.startswith(at) else msg
        groups.setdefault(shape, []).append((at, msg))
    rows = []
    for shape, items in groups.items():
        if len(items) == 1:
            rows.append(finding_li("note", "note", items[0][1]))
            continue
        text = esc(shape).replace("\0", "<em>&lt;node&gt;</em>")
        listed = "".join(f"<li>{esc(at)}</li>" for at, _ in items)
        rows.append(f'<li class="f-note"><span class="tag">note</span><span>{text}'
                    f'<details><summary>{plural(len(items), "node")}</summary>'
                    f'<ul>{listed}</ul></details></span></li>')
    return (f'<ul class="findings">{"".join(rows)}</ul>' if rows
            else '<p class="quiet">Nothing to report.</p>')


def count_cell(value, name=None, attn=True, title=""):
    """A number in a table cell: faint when zero, highlighted when it asks for work."""
    data = f' data-count="{name}"' if name else ""
    cls = "z" if not value else "n" if attn else ""
    hover = f' title="{esc(title)}"' if title else ""
    return f'<td{hover}><span class="{cls}"{data}>{value}</span></td>'


def inbox_cells(info):
    if info is None:
        return '<td class="z">–</td><td class="z">–</td>'
    cells = count_cell(info["count"], "inbox")
    if not info["count"]:
        return cells + '<td class="z">–</td>'
    if "ages" in unchecked:
        return cells + '<td class="quiet" title="oldest not checked: git failed">not checked</td>'
    if info["days"] is None:
        return cells + '<td class="z">–</td>'
    oldest = info["oldest"].isoformat() if info["oldest"] else ""
    return cells + f'<td title="{esc(oldest)}">{plural(info["days"], "day")}</td>'


def local_cell(paths, in_git):
    if not in_git or "local" in unchecked:
        return '<td class="quiet">not checked</td>'
    return count_cell(len(paths), "local", attn=False)


DRIVE_CHIPS = {"linked": ("c-ok", "linked"), "unused docs/": ("c-muted", "unused")}


def drive_cell(f):
    drive = f.get("drive")
    if not drive:
        return '<td class="z">–</td>'
    cls, word = DRIVE_CHIPS.get(drive, ("c-bad", drive))
    title = f.get("drive_root") or f.get("artifacts") or ""
    return (f'<td><span class="chip {cls}" title="{esc(title)}">{esc(word)}</span></td>')


def node_row(node, in_git):
    f = facts.get(node, {})
    depth = max(node.count("/") - 1, 0)
    leaf = node.rsplit("/", 1)[-1]
    chips = ""
    for cls, word, items in (("bad", "problem", problems), ("warn", "warning", warns)):
        k = sum(1 for at, _ in items if at == node)
        if k:
            chips += f'<span class="chip c-{cls}">{plural(k, word)}</span>'
    if f.get("legacy"):
        chips += '<span class="chip c-muted" title="legacy _tmp/">_tmp</span>'
    branch = '<span class="branch">└</span>' if depth else ""
    undistilled = f.get("undistilled")
    limbo = f.get("limbo", [])
    return (f'<tr class="{"top-node" if not depth else "child"}" data-node="{esc(node)}" '
            f'style="--depth: {depth}">'
            f'<td class="name" title="{esc(node)}/">{branch}<span class="mono">{esc(leaf)}'
            f'</span>{chips}</td>'
            + inbox_cells(f.get("inbox"))
            + ('<td class="z">–</td>' if undistilled is None else
               count_cell(undistilled, "undistilled"))
            + count_cell(len(limbo), attn=False, title=", ".join(limbo))
            + local_cell(f.get("local_only", []), in_git)
            + drive_cell(f)
            + "</tr>")


def nodes_html(found, in_git):
    if not found:
        return '<p class="quiet">No nodes yet.</p>'
    rows = "".join(node_row(key(n), in_git) for n in sorted(found))
    head = ("<tr><th>Node</th><th>Inbox</th><th>Oldest</th><th>Undistilled</th>"
            "<th>Limbo</th><th>Local only</th><th>Drive</th></tr>")
    notes = []
    if "ages" in unchecked:
        notes.append("Inbox ages: oldest not checked: git failed.")
    if in_git and "local" in unchecked:
        notes.append("Files only on this machine: not checked: git failed.")
    foot = "".join(f'<p class="footnote">{n}</p>' for n in notes)
    return (f'<div class="scroll"><table><thead>{head}</thead><tbody>{rows}</tbody>'
            f'</table></div>{foot}')


def inbox_html(info):
    if info is None:
        return '<span class="quiet">no inbox</span>'
    if not info["count"]:
        return '<span data-count="inbox">0</span> <span class="quiet">items</span>'
    if "ages" in unchecked:
        age = ' · <span class="quiet">oldest not checked: git failed</span>'
    elif info["oldest"]:
        age = esc(f' · oldest {info["oldest"].isoformat()} ({plural(info["days"], "day")})')
    else:
        age = ""
    return f'<strong class="n" data-count="inbox">{info["count"]}</strong> item(s){age}'


def local_html(paths, in_git):
    if not in_git:
        return '<span class="quiet">not checked without git</span>'
    if "local" in unchecked:
        return '<span class="quiet">not checked: git failed</span>'
    if not paths:
        return '<span data-count="local">0</span> <span class="quiet">files</span>'
    items = "".join(f"<li>{esc(p)}</li>" for p in paths)
    return (f'<details><summary><strong data-count="local">{len(paths)}</strong> '
            f'file(s), ignored by git</summary><ul>{items}</ul></details>')


def facts_html(rows):
    return ('<dl class="facts">' +
            "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows) + "</dl>")


def brain_html(found, git_mode):
    f = facts.get(None, {})
    if git_mode == "skipped":
        remote = identity = '<span class="quiet">not checked (--no-git)</span>'
    elif f.get("git"):
        remote = identity = esc(f["git"])
    else:
        remote, identity = esc(f.get("remote", "?")), esc(f.get("identity", "?"))
    rows = [("Git remote", remote), ("Git identity", identity)]
    if pathlib.Path(ROOT_INBOX).is_dir():
        rows.append((f"{ROOT_INBOX}/", inbox_html(f.get("inbox"))))
    rows.append(("Outside any node, only on this machine",
                 local_html(f.get("local_only", []), git_mode == "used")))
    # Every node's machine-local files in one list: the table only counts them.
    if git_mode == "used" and "local" not in unchecked:
        spread = [p for n in sorted(found)
                  for p in facts.get(key(n), {}).get("local_only", [])]
        if spread:
            items = "".join(f"<li>{esc(p)}</li>" for p in spread)
            rows.append(("In nodes, only on this machine",
                         f'<details><summary>{plural(len(spread), "file")}</summary>'
                         f'<ul>{items}</ul></details>'))
    return f'<div data-node="(brain)">{facts_html(rows)}</div>'


def tiles_html(found, git_mode):
    every = [facts.get(key(n), {}) for n in found] + [facts.get(None, {})]
    inbox = [f["inbox"] for f in every if f.get("inbox")]
    oldest = max((i["days"] for i in inbox if i["days"] is not None), default=None)
    waiting = sum(i["count"] for i in inbox)
    undistilled = sum(f.get("undistilled", 0) for f in every)
    tiles = [
        ("problems", len(problems), "Problems", "bad"),
        ("warnings", len(warns), "Warnings", "warn"),
        ("notes", len(notes), "Notes", ""),
        ("inbox", waiting, "Inbox items", "attn"),
        ("oldest", "–" if oldest is None else oldest,
         "Days the oldest has waited" + (" · not checked" if "ages" in unchecked else ""),
         "attn"),
        ("undistilled", undistilled, "Undistilled log entries", "attn"),
        ("limbo", sum(len(f.get("limbo", [])) for f in every), "Limbo folders", ""),
    ]
    if git_mode == "used" and "local" not in unchecked:
        tiles.append(("local", sum(len(f.get("local_only", [])) for f in every),
                      "Files only on this machine", ""))
    else:
        tiles.append(("local", "–", "Files only on this machine · not checked", ""))
    out = []
    for name, value, label, cls in tiles:
        if not value or value == "–":
            cls = "zero"
        out.append(f'<div class="tile {cls}"><div class="num" data-total="{name}">{value}'
                   f'</div><div class="label">{label}</div></div>')
    return "".join(out)


def write_report(found, git_mode, verdict):
    """Render the status page from this run's findings and facts, then swap it in."""
    try:
        template = string.Template(TEMPLATE.read_text(encoding="utf-8"))
    except OSError as e:
        sys.exit(f"cannot read the status page template: {e}")
    now = datetime.datetime.now().astimezone()
    page = template.substitute(
        brain=esc(brain_name()),
        generated=esc(now.isoformat(sep=" ", timespec="minutes")),
        host=esc(platform.node() or "an unnamed machine"),
        verdict_class="bad" if problems else "ok",
        verdict=esc(verdict),
        tiles=tiles_html(found, git_mode),
        attention=attention_html(),
        nodes=nodes_html(found, git_mode == "used"),
        node_count=len(found),
        brain_section=brain_html(found, git_mode),
        notes=notes_html(),
    )
    tmp = pathlib.Path(f".{REPORT}.tmp")
    try:
        tmp.write_text(page, encoding="utf-8")
        os.replace(tmp, REPORT)
    except OSError as e:
        sys.exit(f"cannot write {REPORT}: {e}")


# --- main ------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    for a in args:
        if a not in ("--git", "--no-git", "--report"):
            sys.exit(f"usage: check-structure.py [--no-git] [--report]\nunknown option {a}")

    root = pathlib.Path("spaces")
    if not root.is_dir():
        sys.exit("no spaces/ -- run from the repo root. Every brain has spaces/ at its "
                 "root; it is where all content lives")

    if pathlib.Path("areas").exists():
        problem("legacy areas/ exists beside spaces/ -- new Itakua brains use only "
                "spaces/. Do not migrate an existing brain without owner approval")

    in_git = "--no-git" not in args and git("rev-parse", "--git-dir") is not None
    found = scan(root)
    check_nodes(found)
    pairs = inboxes(found)
    check_inbox(pairs, first_added(pairs) if in_git else {})
    check_distilled(found)
    check_artifacts(found)
    check_artifact_store(found)
    if in_git:
        check_local_only()
        check_sizes()
        check_allowlist(found)
    if "--no-git" not in args:
        check_git()
    if "--report" in args and in_git and \
            git_ignores(f"The {REPORT} ignore rule", REPORT) is False:
        warn(f"{REPORT} is not gitignored -- add /{REPORT} to .gitignore; the page is "
             f"regenerated per machine and is never committed")

    print(f"{len(found)} nodes checked: " + ", ".join(str(n) for n in sorted(found)))
    for _, m in notes:
        print(f"  note     {m}")
    for _, m in warns:
        print(f"  WARN     {m}")
    for _, m in problems:
        print(f"  PROBLEM  {m}")
    tail = f" {len(warns)} warning(s)." if warns else ""
    verdict = ("OK -- structure and bindings are consistent." + tail if not problems
               else f"{len(problems)} problem(s).{tail}")
    print("\n" + verdict)
    if "--report" in args:
        write_report(found, "skipped" if "--no-git" in args else
                     "used" if in_git else "unavailable", verdict)
        print(f"wrote {REPORT}")
    return 1 if problems else 0


sys.exit(main())
