#!/usr/bin/env python3
"""Check how a brain travels between machines against what its README declares.

    python3 <itakua-sync>/scripts/check-sync.py      # from the brain root

A brain needs no sync. This script reads the Sync row of the root README's bindings
table, looks at what is actually carrying the folder -- a git repository, a Syncthing
folder marker, a path inside iCloud Drive, Dropbox, Google Drive or OneDrive -- and
reports the difference. "none, deliberately" is a boundary: any sync in sight is a
PROBLEM, because that declaration is the whole control.

For git it compares the remote and the repository-local identity with the bindings,
probes the ignore rules the itakua-sync skill gives (inbox binaries, docs/drive,
.drive-map.local, status.html), lists the files that exist only on this machine, and
warns on tracked files over 1 MB in a slot. For Syncthing it reads .stignore for the same
exclusions. For Dropbox it reads the per-path ignore attribute on each docs/drive where
it can. For every tool it lists conflict copies. A query that fails or times out is a
WARN and "not checked", never zero, which would be an all-clear.

Text only. Nothing is written.
"""
import os, sys, re, pathlib, subprocess, shutil, unicodedata

SLOTS = ("notes", "log", "docs", "inbox")
ROOT_INBOX = "00-inbox"
LARGE = 1024 * 1024              # a tracked file in a slot above this gets a warning
TIMEOUT = 10                     # seconds; a slower query is reported, never read as empty
TOOLS = ("git", "syncthing", "dropbox", "icloud")
# Files every sync must leave on this machine, besides docs/drive.
LOCAL_ONLY = (".drive-map.local", "status.html")
# Folders a cloud client carries, by a component of the brain's absolute path.
CLOUD_FOLDERS = (
    ("icloud", re.compile(r"^(Mobile Documents|com~apple~CloudDocs|iCloud Drive)$")),
    ("dropbox", re.compile(r"^Dropbox")),
    ("google drive", re.compile(r"^(Google Drive|GoogleDrive-.*|My Drive)$")),
    ("onedrive", re.compile(r"^OneDrive")),
)
CONFLICT = (
    ("syncthing", re.compile(r"\.sync-conflict-\d{8}-\d{6}")),
    ("dropbox", re.compile(r" \(.*conflicted copy.*\)")),
)
ICLOUD_COPY = re.compile(r"^(.*) (\d+)(\.[^.]+)?$")

problems, warns, notes = [], [], []


def problem(msg): problems.append(msg)
def warn(msg): warns.append(msg)
def note(msg): notes.append(msg)


def nfc(text):
    return unicodedata.normalize("NFC", text)


# --- what the README declares -----------------------------------------------------

def declared_bindings():
    """The bindings table's first two columns, keyed by the lowercased binding name."""
    out = {}
    readme = pathlib.Path("README.md")
    if not readme.is_file():
        return out
    for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2:
            out[cells[0].replace("*", "").strip().lower()] = cells[1]
    return out


def declared_sync(bindings):
    """(tools, deliberate): the tools the Sync row names, and whether 'none' is a boundary.

    An absent row reads as none, not deliberately: a brain that predates the row.
    """
    cell = bindings.get("sync", "").lower()
    tools = {t for t in TOOLS if re.search(rf"\b{t}\b", cell)}
    deliberate = bool(re.search(r"\bnone\b", cell)) and "deliberate" in cell
    return tools, deliberate


# --- what is actually carrying the folder -----------------------------------------

def run(*cmd):
    """(result, None), or (None, reason) when the command cannot run or times out."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT,
                              stdin=subprocess.DEVNULL), None
    except subprocess.TimeoutExpired:
        return None, f"timed out after {TIMEOUT} s"
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e) or type(e).__name__


def git_query(what, *args):
    """git's stdout, or None after a WARN: a failed query is never an empty answer."""
    result, reason = run("git", *args)
    if result is not None and result.returncode == 0:
        return result.stdout
    if result is not None:
        reason = (result.stderr.strip().splitlines() or [f"exit {result.returncode}"])[0]
    warn(f"{what} not checked: `git {args[0]}` failed ({reason})")
    return None


def git_ignores(what, path):
    """True or False, or None after a WARN when git cannot say."""
    result, reason = run("git", "check-ignore", "-q", "--no-index", path)
    if result is not None and result.returncode in (0, 1):
        return result.returncode == 0
    if result is not None:
        reason = (result.stderr.strip().splitlines() or [f"exit {result.returncode}"])[0]
    warn(f"{what} not checked: `git check-ignore` failed ({reason})")
    return None


def git_config(*args):
    """A config value, or "" when unset or unreadable: absent and failed read the same."""
    result, _ = run("git", "config", *args)
    return result.stdout.strip() if result is not None and result.returncode == 0 else ""


def in_git():
    """Whether this folder is the top of a git repository. A brain inside a bigger
    repository is noted: its rules then live in a .gitignore it does not own."""
    if not pathlib.Path(".git").exists():
        return False
    top = git_query("Git repository", "rev-parse", "--show-toplevel")
    if top is None:
        return True
    if os.path.realpath(top.strip()) != os.path.realpath("."):
        note(f"the brain is inside the git repository at {top.strip()}, not one of its own")
    return True


def cloud_folders():
    """The cloud clients whose folders this brain sits in, from its absolute path."""
    found = []
    for part in pathlib.Path.cwd().resolve().parts:
        for name, pattern in CLOUD_FOLDERS:
            if pattern.match(part) and name not in found:
                found.append(name)
    return found


def detected():
    """Every sync in sight, as {name: evidence}."""
    seen = {}
    if in_git():
        seen["git"] = ".git/"
    if pathlib.Path(".stfolder").is_dir():
        seen["syncthing"] = ".stfolder/ marker"
    elif pathlib.Path(".stignore").is_file():
        seen["syncthing"] = ".stignore"
    if pathlib.Path(".dropbox").exists():
        seen["dropbox"] = ".dropbox"
    for name in cloud_folders():
        seen.setdefault(name, "the folder's path")
    return seen


# --- the tree ------------------------------------------------------------------------

def walk():
    """Every file in the brain, as a relative POSIX path. docs/drive is never entered."""
    for dirpath, dirnames, filenames in os.walk("."):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in (".git", ".stfolder", ".stversions")
                             and not (d == "drive" and os.path.basename(dirpath) == "docs"))
        for f in sorted(filenames):
            yield os.path.relpath(os.path.join(dirpath, f), ".").replace(os.sep, "/")


def drive_links():
    """Every node's docs/drive link under spaces/."""
    links = []
    for dirpath, dirnames, _ in os.walk("spaces"):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        if os.path.basename(dirpath) == "docs":
            link = pathlib.Path(dirpath, "drive")
            if link.is_symlink():
                links.append(link.as_posix())
            dirnames[:] = []
    return links


def check_conflicts(tools):
    """Conflict copies, by the tool that makes them. iCloud's `name 2.md` is only reported
    when the brain sits in iCloud, since the shape is an ordinary file name elsewhere."""
    copies = {}
    files = list(walk())
    present = set(files)
    for path in files:
        base = os.path.basename(path)
        for tool, pattern in CONFLICT:
            if pattern.search(base):
                copies.setdefault(tool, []).append(path)
        m = ICLOUD_COPY.match(base)
        if "icloud" in tools and m and \
                f"{os.path.dirname(path)}/{m.group(1)}{m.group(3) or ''}".lstrip("/") in present:
            copies.setdefault("icloud", []).append(path)
    for tool, paths in sorted(copies.items()):
        shown = ", ".join(paths[:5]) + (f", and {len(paths) - 5} more" if len(paths) > 5 else "")
        warn(f"{len(paths)} {tool} conflict cop{'y' if len(paths) == 1 else 'ies'}: {shown} "
             f"-- read both sides; resolving one is an edit that needs owner approval")


# --- git ----------------------------------------------------------------------------

def check_git(bindings):
    remotes = git_query("Git remote", "remote")
    listed = None if remotes is None else [r for r in remotes.splitlines() if r.strip()]
    declared = bindings.get("git remote", "")
    if listed:
        urls = ", ".join(f"{r} -> {git_config(f'remote.{r}.url') or '?'}" for r in listed)
        if re.search(r"\bnone\b", declared, re.I) and "none yet" not in declared.lower():
            problem(f"README declares NO git remote, and {len(listed)} is configured: {urls}")
        else:
            note(f"git remote(s): {urls}")
    elif listed is not None:
        note("git: no remote configured")

    local_mail = git_config("--local", "user.email")
    local_name = git_config("--local", "user.name")
    global_mail = git_config("--global", "user.email")
    want = re.search(r"([^<>|*]+?)\s*<([^<>@\s]+@[^<>@\s]+)>", bindings.get("git identity", ""))
    if not local_mail:
        if global_mail:
            problem(f"no repository-local git identity -- commits here will be authored as "
                    f"the GLOBAL identity <{global_mail}>; set one: git config --local "
                    f"user.email you@example.com")
        else:
            problem("no git identity, local or global -- set a repository-local one before "
                    "committing")
    elif want and want.group(2) != local_mail:
        problem(f"README declares git identity <{want.group(2)}>, the repository is "
                f"configured as <{local_mail}>")
    elif want and want.group(1).strip() != local_name:
        note(f"README declares git name '{want.group(1).strip()}', the repository has "
             f"'{local_name}'")
    else:
        note(f"git identity: {local_name} <{local_mail}>"
             + ("" if want else " (README declares none)"))

    # --- what .gitignore keeps out ---
    probes = [("inbox binaries", "spaces/node/inbox/capture.heic"),
              (f"{ROOT_INBOX}/ binaries", f"{ROOT_INBOX}/capture.heic"),
              ("docs/drive", "spaces/node/docs/drive")]
    probes += [(name, name) for name in LOCAL_ONLY]
    for what, probe in probes:
        if git_ignores(f"The .gitignore rule for {what}", probe) is False:
            warn(f".gitignore does not keep {what} out of history ({probe} is not ignored) "
                 f"-- add the block the itakua-sync skill gives")

    # --- files only on this machine ---
    out = git_query("Files only on this machine", "ls-files", "-z", "-o", "-i",
                    "--exclude-standard", "--", "spaces", ROOT_INBOX)
    if out is not None:
        local = [p for p in out.split("\0") if p
                 and not any(part.startswith(".") for part in p.split("/"))
                 and not p.endswith("/docs/drive")]
        if local:
            shown = ", ".join(local[:5]) + (f", and {len(local) - 5} more" if len(local) > 5 else "")
            note(f"{len(local)} file(s) only on this machine (ignored by git, outside "
                 f"docs/drive): {shown}")

    # --- tracked files that weigh on history ---
    out = git_query("Tracked files over 1 MB", "ls-files", "-z", "--", "spaces")
    for path in (out or "").split("\0"):
        parts = path.split("/")
        if not path or not any(p in SLOTS for p in parts[2:-1]):
            continue
        try:
            size = os.lstat(path).st_size
        except OSError:
            continue
        if size > LARGE:
            warn(f"{path} is {size / LARGE:.1f} MB and tracked by git -- history keeps "
                 f"every version; move it to docs/drive unless it must be versioned")


# --- syncthing ------------------------------------------------------------------------

def check_syncthing():
    ignore = pathlib.Path(".stignore")
    if not ignore.is_file():
        warn("no .stignore at the brain root -- Syncthing would carry docs/drive, "
             ".drive-map.local and status.html; write one from the itakua-sync table")
        return
    text = ignore.read_text(encoding="utf-8", errors="replace")
    rules = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("//")]
    for what in ("docs/drive",) + LOCAL_ONLY:
        if not any(what in r for r in rules):
            warn(f".stignore has no rule for {what} -- Syncthing would carry it; the first "
                 f"matching pattern wins, so put the exclusion before any include")
    note(f".stignore read: {len(rules)} rule(s). It is never synced itself; make sure every "
         f"machine has one")


# --- dropbox -------------------------------------------------------------------------

def check_dropbox():
    xattr = shutil.which("xattr")
    links = drive_links()
    if not links:
        return
    if not xattr:
        warn(f"Dropbox ignore attribute not checked on {len(links)} docs/drive link(s): no "
             f"xattr command here -- verify each is excluded from the Dropbox client")
        return
    for link in links:
        result, _ = run(xattr, "-p", "com.dropbox.ignored", link)
        if result is None or result.returncode != 0 or result.stdout.strip() != "1":
            warn(f"{link} carries no com.dropbox.ignored attribute -- Dropbox may follow "
                 f"the link and copy the whole Drive folder: "
                 f"xattr -w com.dropbox.ignored 1 {link}")


# --- main ---------------------------------------------------------------------------

def main():
    if sys.argv[1:]:
        sys.exit("usage: check-sync.py  (from the brain root; takes no options)")
    if not pathlib.Path("spaces").is_dir():
        sys.exit("no spaces/ -- run from the brain root")

    bindings = declared_bindings()
    tools, deliberate = declared_sync(bindings)
    seen = detected()
    declared = ", ".join(sorted(tools)) or ("none, deliberately" if deliberate else "none")
    print(f"sync declared: {declared}; found: "
          + (", ".join(f"{k} ({v})" for k, v in seen.items()) or "nothing"))

    if deliberate:
        for name, evidence in seen.items():
            problem(f"README declares sync none, deliberately, but {name} is in sight "
                    f"({evidence}) -- this brain's material must not leave the machine")
    else:
        for name in seen:
            if name not in tools:
                note(f"{name} carries this folder ({seen[name]}) but the README's Sync row "
                     f"does not say so -- update the row, with owner approval")
    for tool in sorted(tools):
        if tool == "git" and "git" not in seen:
            problem("README declares git, but this folder is not a git repository")
        elif tool != "git" and tool not in seen:
            note(f"README declares {tool}, which is not set up on this machine")

    if "git" in seen:
        check_git(bindings)
    if "syncthing" in seen or "syncthing" in tools:
        check_syncthing()
    if "dropbox" in seen or "dropbox" in tools:
        check_dropbox()
    if "icloud" in seen or "icloud" in tools:
        for link in drive_links():
            note(f"{link}: how iCloud treats this link is untested -- confirm on a second "
                 f"device what arrived before relying on it")
    check_conflicts(set(tools) | set(seen))

    for m in notes:
        print(f"  note     {m}")
    for m in warns:
        print(f"  WARN     {m}")
    for m in problems:
        print(f"  PROBLEM  {m}")
    tail = f" {len(warns)} warning(s)." if warns else ""
    print("\n" + ("OK -- sync matches the README." + tail if not problems
                  else f"{len(problems)} problem(s).{tail}"))
    return 1 if problems else 0


sys.exit(main())
