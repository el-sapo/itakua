#!/usr/bin/env python3
"""Validate a brain against the four-slot framework.

    python3 <itakua-map>/scripts/check-structure.py          # structure
    python3 <itakua-map>/scripts/check-structure.py --report # also write status.html

A folder is either a SLOT (notes/ log/ docs/ inbox/) directly inside a node, something
filed INSIDE a slot, or a CHILD NODE (it has its own README.md). Any other folder inside a
node is LIMBO: the owner's, reported as a note and never a failure. A folder under spaces/
whose parent is not a node is still a problem: that is a node missing its README.

A node whose docs/drive is linked declares where that folder lives in Drive with an
`artifacts:` key in its README frontmatter. Readers that cannot follow the symlink -- the
Reader, an agent on the MCP server -- have nothing else to go on. A missing, stale or
orphaned key is a WARNING: the key is optional; a fresh clone has it before the symlink.
Its optional `url` is the folder's Drive link, because a path is not one. On macOS, Drive
for Desktop may keep the folder's Drive id in the com.google.drivefs.item-id#S attribute;
where this machine can read it, a missing url is proposed and a contradicting one warned.
Where it cannot -- Drive not running, another OS, a folder that does not carry it --
nothing is said about url beyond the shape of a declared one.

Structure only. A brain is a folder of plain files and needs no sync; whatever carries it
between machines is checked by the itakua-sync skill's own script, never from here.

--report writes status.html at the brain root once the checks finish: the same findings,
plus each node's inbox, undistilled log entries and limbo, as one static page from
assets/status-page.html. Without it the validator writes nothing.
"""
import os, sys, json, pathlib, re, subprocess, unicodedata, datetime, html, platform
import shutil, string, urllib.parse

SLOTS = ("notes", "log", "docs", "inbox")
REQUIRED = ("notes", "log")
ROOT_INBOX = "00-inbox"
REPORT = "status.html"
TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "assets" / "status-page.html"

# Findings, each as (node, message): node is the NFC path of the node it is about, or None
# for the brain as a whole. The text output and the status page both read these lists.
problems, warns, notes = [], [], []
# What the status page shows beside the findings, by node (None is the brain). Filled by
# the same checks that print, so every number on the page is one the text output gave.
facts = {}
# Every directory under spaces/, NFC-keyed: container, node, slot, inslot, limbo
# or orphan. Kept after the walk so later checks can tell slot content from limbo.
status = {}


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
        elif pstat == "orphan":
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


def captured_at(item):
    """The `captured_at:` a capture declares, as a timestamp, or None.

    Only a .md item is read, and only its frontmatter; a value that does not parse as an
    ISO 8601 date or datetime is ignored, as is anything else about the file.
    """
    if item.suffix.lower() != ".md":
        return None
    try:
        with open(item, encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
    except OSError:
        return None
    for line in frontmatter(head):
        m = re.match(r"captured_at:(.*)$", line)
        if not m:
            continue
        value = scalar(m.group(1)) or ""
        try:
            when = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if when.tzinfo is None:
            when = when.astimezone()
        return when.timestamp()
    return None


def check_inbox(pairs):
    """One note per inbox with something in it: how many, and since when.

    An item has waited since it arrived: the earlier of its ctime, which a move, copy or
    download sets, and the `captured_at` a capture declares. Never mtime: a 2019 PDF
    dropped in today has not waited since 2019. ctime also moves on any metadata change
    (an edit, a chmod, an app tagging the file it opens), so an item can look newer than
    it is, never older; a capture's own stamp survives that, and a fresh copy of a brain.
    """
    today = datetime.date.today()
    for node, inbox in pairs:
        items = inbox_items(inbox)
        stamps = []
        for item in items:
            times = [t for t in (captured_at(item),) if t is not None]
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
            age = f", oldest {oldest.isoformat()} ({days} day(s))" if oldest else ""
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


# --- helpers ----------------------------------------------------------------------

def node_of(path):
    """The nearest node at or above `path`, or None when it is not inside one."""
    d = nfc(path)
    while d and d != ".":
        if status.get(d) == "node":
            return d
        d = os.path.dirname(d)
    return None


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
# A Drive id, as index-artifacts.py reads one, and the folder link a reader opens.
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,}")
FOLDER_URL = "https://drive.google.com/drive/folders/{}"
# Where Drive for Desktop on macOS keeps a synced item's Drive id.
ITEM_ID_XATTR = "com.google.drivefs.item-id#S"
XATTR_TIMEOUT = 5                # seconds; a slower answer counts as none
# How Drive for Desktop is reported to mark the id of an item still uploading. No real
# Drive id starts this way; one that did would be a link that opens nothing.
TEMPORARY_ID = "local-"


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

    Not a YAML parser, on purpose: frontmatter stays flat apart from this one small
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
    """'/Users/x/.../GoogleDrive-x/My Drive/House' -> 'My Drive/House', else None."""
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


def drive_item_id(path):
    """The Drive id Drive for Desktop keeps on `path`, or None when it cannot be read.

    On macOS it is the extended attribute com.google.drivefs.item-id#S, read with Apple's
    xattr on the resolved path, so nothing depends on xattr following a symlink. That is
    confirmed for files, not yet for folders, so None is an ordinary answer: no command,
    no Drive, no attribute, an error, a timeout, an answer not shaped like a Drive id, or
    a temporary one (local-...) for an item still uploading. None of those is ever output.
    """
    xattr = shutil.which("xattr")
    if not xattr:
        return None
    try:
        result = subprocess.run((xattr, "-p", ITEM_ID_XATTR, os.path.realpath(path)),
                                stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=XATTR_TIMEOUT)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    value = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode != 0 or value.startswith(TEMPORARY_ID):
        return None
    return value if DRIVE_ID.fullmatch(value) else None


def folder_link_id(url):
    """The folder id in a declared `artifacts.url`, or (None, what is wrong with it).

    Drive's Copy link on a folder gives https://drive.google.com/drive/folders/<id>,
    sometimes with /u/<n>/ before `folders` and a query (?usp=sharing, ?usp=drive_link,
    resourcekey=); all of those read. Anything else is reported, and never compared.
    """
    if url is None:
        return None, "cannot be read"
    if "<" in url or ">" in url:
        return None, f"is still a placeholder: {url}"
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None, f"is not a Drive folder link: {url}"
    if parts.scheme.lower() != "https":
        return None, f"is not an https link: {url}"
    path = re.fullmatch(r"/drive/(?:u/\d+/)?folders(?:/([^/]*))?/?", parts.path)
    if parts.netloc.lower() != "drive.google.com" or not path or UNPRINTABLE.search(url):
        return None, f"is not a Drive folder link: {url}"
    if not DRIVE_ID.fullmatch(path.group(1) or ""):
        return None, f"carries no folder id: {url}"
    return path.group(1), None


def check_artifact_url(declared, readme, drive, folder, at):
    """Compare a declared `artifacts.url` with the Drive id of the folder docs/drive
    points to, `folder`. A missing url is only a note, and only where that id is
    readable: the key is optional, the owner may leave it out on purpose, and a url is
    never guessed. A url that is unusable or names another folder is a warning."""
    url = declared.get("url", "")
    if url == "":
        if folder:
            note(f"{readme} `artifacts:` has no `url` (optional); from the Drive id of the "
                 f"folder {drive} points to, it would be `url: {FOLDER_URL.format(folder)}`. "
                 f"Adding it is a README edit: owner approval", node=at)
        return
    declared_id, wrong = folder_link_id(url)
    if wrong:
        fix = (f"; from the Drive id of the folder {drive} points to, propose "
               f"`url: {FOLDER_URL.format(folder)}`" if folder else
               "; take it from Drive's Copy link on the folder itself")
        warn(f"{readme} `artifacts.url` {wrong}{fix}. Correcting it is a README edit: "
             f"owner approval", node=at)
    elif folder and declared_id != folder:
        warn(f"{readme} declares `artifacts.url` for Drive folder {declared_id}, but the "
             f"folder {drive} points to has id {folder} -- correct whichever is stale, "
             f"with owner approval", node=at)


def check_artifact_store(found):
    """Compare each README's `artifacts:` key with the node's docs/drive link."""
    for n in found:
        readme = n / "README.md"
        declared = declared_artifacts(readme.read_text(encoding="utf-8"))
        drive = n / "docs" / "drive"
        root, source = mapped_root(n, drive)
        folder = drive_item_id(drive) if drive.is_symlink() and drive.is_dir() else None
        at = key(n)
        if root:
            fact(at)["drive_root"] = root

        if declared is None:
            if drive.is_symlink():
                proposal = (f"; from {source}, propose `provider: google-drive` and "
                            f"`root: {yaml_scalar(root)}`" if root else
                            "; set `root` to the Drive folder docs/drive points to, as "
                            "Drive shows it")
                if folder:
                    proposal += (f"; from that folder's Drive id, "
                                 f"`url: {FOLDER_URL.format(folder)}`")
                warn(f"{n}/ has docs/drive but {readme} declares no `artifacts:` "
                     f"key{proposal}. Adding it is a README edit: owner approval", node=at)
            continue

        declared_root = nfc(declared.get("root") or "").strip("/")
        provider = declared.get("provider") or ""
        fact(at)["artifacts"] = declared_root
        if not declared_root:
            warn(f"{readme} has an `artifacts:` key with no readable `root` -- use the "
                 f"block form the itakua-map skill defines, indented with spaces, "
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
        check_artifact_url(declared, readme, drive, folder, at)


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

    Ten nodes with the same limbo folder make ten notes that say the same thing; the page
    shows the sentence once and lists the nodes under it.
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
    if not info["count"] or info["days"] is None:
        return cells + '<td class="z">–</td>'
    oldest = info["oldest"].isoformat() if info["oldest"] else ""
    return cells + f'<td title="{esc(oldest)}">{plural(info["days"], "day")}</td>'


DRIVE_CHIPS = {"linked": ("c-ok", "linked"), "unused docs/": ("c-muted", "unused")}


def drive_cell(f):
    drive = f.get("drive")
    if not drive:
        return '<td class="z">–</td>'
    cls, word = DRIVE_CHIPS.get(drive, ("c-bad", drive))
    title = f.get("drive_root") or f.get("artifacts") or ""
    return (f'<td><span class="chip {cls}" title="{esc(title)}">{esc(word)}</span></td>')


def node_row(node):
    f = facts.get(node, {})
    depth = max(node.count("/") - 1, 0)
    leaf = node.rsplit("/", 1)[-1]
    chips = ""
    for cls, word, items in (("bad", "problem", problems), ("warn", "warning", warns)):
        k = sum(1 for at, _ in items if at == node)
        if k:
            chips += f'<span class="chip c-{cls}">{plural(k, word)}</span>'
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
            + drive_cell(f)
            + "</tr>")


def nodes_html(found):
    if not found:
        return '<p class="quiet">No nodes yet.</p>'
    rows = "".join(node_row(key(n)) for n in sorted(found))
    head = ("<tr><th>Node</th><th>Inbox</th><th>Oldest</th><th>Undistilled</th>"
            "<th>Limbo</th><th>Drive</th></tr>")
    return (f'<div class="scroll"><table><thead>{head}</thead><tbody>{rows}</tbody>'
            f'</table></div>')


def inbox_html(info):
    if info is None:
        return '<span class="quiet">no inbox</span>'
    if not info["count"]:
        return '<span data-count="inbox">0</span> <span class="quiet">items</span>'
    if info["oldest"]:
        age = esc(f' · oldest {info["oldest"].isoformat()} ({plural(info["days"], "day")})')
    else:
        age = ""
    return f'<strong class="n" data-count="inbox">{info["count"]}</strong> item(s){age}'


def facts_html(rows):
    return ('<dl class="facts">' +
            "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows) + "</dl>")


def brain_html():
    f = facts.get(None, {})
    rows = [("Path", esc(pathlib.Path.cwd()))]
    if pathlib.Path(ROOT_INBOX).is_dir():
        rows.append((f"{ROOT_INBOX}/", inbox_html(f.get("inbox"))))
    return f'<div data-node="(brain)">{facts_html(rows)}</div>'


def tiles_html(found):
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
        ("oldest", "–" if oldest is None else oldest, "Days the oldest has waited", "attn"),
        ("undistilled", undistilled, "Undistilled log entries", "attn"),
        ("limbo", sum(len(f.get("limbo", [])) for f in every), "Limbo folders", ""),
    ]
    out = []
    for name, value, label, cls in tiles:
        if not value or value == "–":
            cls = "zero"
        out.append(f'<div class="tile {cls}"><div class="num" data-total="{name}">{value}'
                   f'</div><div class="label">{label}</div></div>')
    return "".join(out)


def write_report(found, verdict):
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
        tiles=tiles_html(found),
        attention=attention_html(),
        nodes=nodes_html(found),
        node_count=len(found),
        brain_section=brain_html(),
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
        if a != "--report":
            sys.exit(f"usage: check-structure.py [--report]\nunknown option {a}")

    root = pathlib.Path("spaces")
    if not root.is_dir():
        sys.exit("no spaces/ -- run from the repo root. Every brain has spaces/ at its "
                 "root; it is where all content lives")

    found = scan(root)
    check_nodes(found)
    check_inbox(inboxes(found))
    check_distilled(found)
    check_artifacts(found)
    check_artifact_store(found)

    print(f"{len(found)} nodes checked: " + ", ".join(str(n) for n in sorted(found)))
    for _, m in notes:
        print(f"  note     {m}")
    for _, m in warns:
        print(f"  WARN     {m}")
    for _, m in problems:
        print(f"  PROBLEM  {m}")
    tail = f" {len(warns)} warning(s)." if warns else ""
    verdict = ("OK -- structure is consistent." + tail if not problems
               else f"{len(problems)} problem(s).{tail}")
    print("\n" + verdict)
    if "--report" in args:
        write_report(found, verdict)
        print(f"wrote {REPORT}")
    return 1 if problems else 0


sys.exit(main())
