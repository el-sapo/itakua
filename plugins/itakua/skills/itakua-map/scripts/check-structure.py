#!/usr/bin/env python3
"""Validate a brain against the four-slot framework, and against its own bindings.

    python3 skill/scripts/check-structure.py          # structure + git state
    python3 skill/scripts/check-structure.py --no-git # structure only
    python3 skill/scripts/check-structure.py --stamp  # record skill/ as packaged

A folder is either a SLOT (notes/ log/ docs/ _tmp/) directly inside a node, something
filed INSIDE a slot, or a CHILD NODE (it has its own README.md). Anything else is drift.

The git section exists because the structure was never the part that could hurt you.
A brain declares bindings in its root README -- remote, identity -- and those are the
things whose failure is silent and unrecoverable. Structure problems are a tidy-up;
a work brain pushed to a personal account is not.
"""
import os, sys, pathlib, re, hashlib, subprocess

SLOTS = ("notes", "log", "docs", "_tmp")
REQUIRED = ("notes", "log")
problems, notes = [], []


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
                notes.append(f"{n}/README.md mentions {s}/, which does not exist")
        if (n / "_tmp").is_dir():
            if "## `_tmp/` contract" not in readme:
                problems.append(f"{n}/ has _tmp/ but its README declares no `_tmp/` contract")
            for field in ("**Disposition:**", "**Mode:**"):
                if field not in readme:
                    problems.append(f"{n}/README.md `_tmp/` contract is missing {field}")


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
                f"git config --local user.email you@example.com")
        else:
            problems.append("no git identity, local or global -- commits will fail or "
                            "be authored by a guess. Set a local one")
    else:
        if global_mail and global_mail == local_mail:
            notes.append(f"local identity <{local_mail}> is the same as the global one")
        m = re.search(r"([^<>|*]+?)\s*<([^<>@\s]+@[^<>@\s]+)>", declared.get("git identity", ""))
        if m:
            want_name, want_mail = m.group(1).strip(), m.group(2).strip()
            if want_mail != local_mail:
                problems.append(f"README declares identity <{want_mail}>, repository is "
                                f"configured as <{local_mail}>")
            elif want_name != (local_name or ""):
                notes.append(f"README declares name '{want_name}', repository has "
                             f"'{local_name}'")
            else:
                notes.append(f"identity matches the README: {local_name} <{local_mail}>")
        else:
            notes.append(f"identity: {local_name} <{local_mail}> (README declares none)")

    # --- the spine exists at all ---
    for f in ("README.md", ".gitignore"):
        if not pathlib.Path(f).is_file():
            notes.append(f"no {f} at the repository root")


# --- skill drift -----------------------------------------------------------------

def skill_hashes(skill_dir):
    """Hash the skill's own files.

    Dotfiles are skipped -- they are not skill content, and on macOS one Finder visit
    drops a .DS_Store in here and turns the health check red. `.gitkeep` is the one
    exception: the template's empty slots exist only because of it, so it IS payload.
    `*.local` stays out because it is machine-specific, never packaged.
    """
    out = {}
    for f in sorted(skill_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(skill_dir)
        if any(part.startswith(".") and part != ".gitkeep" for part in rel.parts):
            continue
        if rel.name.endswith(".local"):
            continue
        out[str(rel)] = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
    return out


def check_drift(skill_dir):
    # The installed skill is a COPY, and it is installed per agent ACCOUNT. Editing
    # skill/ here changes neither. skill/.packaged records what went into the last
    # package; if the files have moved on, say so. Note the limit: one stamp cannot
    # know how many accounts installed it, or whether one of them is stale.
    stamp = skill_dir / ".packaged"
    if not skill_dir.is_dir() or not stamp.exists():
        return
    current = skill_hashes(skill_dir)
    recorded = dict(
        line.split("  ", 1)[::-1]
        for line in stamp.read_text().split("\n")
        if line and not line.startswith("#")
    )
    drifted = sorted(k for k in current if recorded.get(k) != current[k])
    gone = sorted(k for k in recorded if k not in current)
    if drifted or gone:
        problems.append(
            "skill/ has changed since it was last packaged: "
            + ", ".join(drifted + [g + " (removed)" for g in gone])
            + " -- re-package and re-install (in EVERY account that has it), or the "
              "installed copy contradicts this repo")


# --- main ------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    for a in args:
        if a not in ("--stamp", "--git", "--no-git"):
            sys.exit(f"usage: check-structure.py [--stamp] [--no-git]\nunknown option {a}")

    if "--stamp" in args:
        # Run this immediately AFTER packaging and installing the skill.
        sd = pathlib.Path("skill")
        if not sd.is_dir():
            sys.exit("no skill/ here -- --stamp only applies in the canonical repo")
        lines = ["# Written by check-structure.py --stamp, right after the skill was packaged",
                 "# and installed. If these hashes stop matching skill/, the installed copy is",
                 "# behind the repo and an agent is following retired rules.",
                 "# NOTE: one stamp, N installed copies -- a skill installs per agent ACCOUNT,",
                 "# and this cannot tell how many exist or whether one was skipped."]
        h = skill_hashes(sd)
        lines += [f"{v}  {k}" for k, v in sorted(h.items())]
        (sd / ".packaged").write_text("\n".join(lines) + "\n")
        print(f"stamped {len(h)} skill files as packaged")
        return 0

    root = pathlib.Path("spaces")
    if not root.is_dir():
        sys.exit("no spaces/ -- run from the repo root. Every brain has spaces/ at its "
                 "root; it is where all content lives")

    if pathlib.Path("areas").exists():
        problems.append("legacy areas/ exists beside spaces/ -- new Itakua brains use only "
                        "spaces/. Do not migrate an existing brain without owner approval")

    found = scan(root)
    check_nodes(found)
    check_drift(pathlib.Path("skill"))
    if "--no-git" not in args:
        check_git()

    print(f"{len(found)} nodes checked: " + ", ".join(str(n) for n in sorted(found)))
    for m in notes:
        print(f"  note     {m}")
    for m in problems:
        print(f"  PROBLEM  {m}")
    print("\nOK -- structure and bindings are consistent." if not problems
          else f"\n{len(problems)} problem(s).")
    return 1 if problems else 0


sys.exit(main())
