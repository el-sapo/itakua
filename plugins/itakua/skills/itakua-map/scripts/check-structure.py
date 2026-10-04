#!/usr/bin/env python3
"""Validate a brain against the four-slot framework, and against its own bindings.

    python3 <itakua-map>/scripts/check-structure.py          # structure + git state
    python3 <itakua-map>/scripts/check-structure.py --no-git # structure only

A folder is either a SLOT (notes/ log/ docs/ _tmp/) directly inside a node, something
filed INSIDE a slot, or a CHILD NODE (it has its own README.md). Anything else is drift.

A node whose docs/drive is linked declares where that folder lives in Drive with an
`artifacts:` key in its README frontmatter. Readers that cannot follow the symlink -- the
Reader, an agent on the MCP server -- have nothing else to go on. A missing, stale or
orphaned key is a WARNING: the key is optional, and a fresh clone has it before the link.

The git section exists because the structure was never the part that could hurt you.
A brain declares bindings in its root README -- remote, identity -- and those are the
things whose failure is silent and unrecoverable. Structure problems are a tidy-up;
a work brain pushed to a personal account is not.
"""
import os, sys, pathlib, re, subprocess, unicodedata

SLOTS = ("notes", "log", "docs", "_tmp")
REQUIRED = ("notes", "log")
problems, warns, notes = [], [], []


# --- structure -------------------------------------------------------------------

def scan(root):
    """Classify every directory under spaces/, top-down.

    A slot is only a slot when its PARENT is a node. Matching the bare name anywhere
    in the path fails open: a node legitimately called `notes` or `log`, or anything
    beneath it, would be skipped by validation entirely.
    """
    found = []
    status = {str(root): "container"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        if dirpath == str(root):
            continue
        parent = os.path.dirname(dirpath)
        base = os.path.basename(dirpath)
        pstat = status.get(parent, "container")

        if pstat in ("slot", "inslot"):
            status[dirpath] = "inslot"
        elif pstat == "orphan":
            status[dirpath] = "orphan"            # already reported at the top
        elif base in SLOTS and pstat == "node":
            status[dirpath] = "slot"
        elif "README.md" in filenames:
            status[dirpath] = "node"
            found.append(pathlib.Path(dirpath))
        else:
            status[dirpath] = "orphan"
            rel = os.path.relpath(dirpath, ".")
            if base in SLOTS:
                problems.append(f"{rel}/ is named like a slot but its parent is not a "
                                f"node -- give the parent a README.md, or rename this")
            else:
                problems.append(f"{rel}/ is neither a slot nor a node (no README.md) -- "
                                f"move its contents into a slot, or give it a README")
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
                detail = " -- load itakua-setup to restore local staging" if s == "_tmp" else ""
                notes.append(f"{n}/README.md mentions {s}/, which does not exist{detail}")
        if (n / "_tmp").is_dir():
            if "## `_tmp/` contract" not in readme:
                problems.append(f"{n}/ has _tmp/ but its README declares no `_tmp/` contract")
            for field in ("**Disposition:**", "**Mode:**"):
                if field not in readme:
                    problems.append(f"{n}/README.md `_tmp/` contract is missing {field}")


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
    """A plain YAML scalar: surrounding quotes removed, or a trailing comment dropped."""
    value = value.strip()
    quoted = re.match(r"""^(["'])(.*)\1(?:\s+#.*)?$""", value)
    if quoted:
        return quoted.group(2)
    if value.startswith("#"):
        return ""
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


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
        if scalar(m.group(1)):
            return fields                          # inline or flow form
        for sub in lines[i + 1:]:
            if not sub.strip() or sub.lstrip().startswith("#"):
                continue
            if not sub[:1].isspace():
                break
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
                            f"`root: {root}`" if root else
                            "; set `root` to the Drive folder docs/drive points to, as "
                            "Drive shows it")
                warns.append(f"{n}/ has docs/drive but {readme} declares no `artifacts:` "
                             f"key{proposal}. Adding it is a README edit: owner approval")
            continue

        declared_root = nfc(declared.get("root", "")).strip("/")
        provider = declared.get("provider", "")
        if not declared_root:
            warns.append(f"{readme} has an `artifacts:` key with no readable `root` -- "
                         f"use the two-line block form the itakua-map skill defines")
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
                         f"gives `{root}` -- correct whichever is stale, with owner approval")


# --- git state -------------------------------------------------------------------

def git(*args):
    try:
        r = subprocess.run(("git",) + args, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


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

    found = scan(root)
    check_nodes(found)
    check_artifacts(found)
    check_artifact_store(found)
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
