"""Behavioral regressions for check-sync.py, the itakua-sync skill's check.

A brain needs no sync, so the first test is that a plain folder passes with nothing said
about any tool. The rest cover the README's Sync row against what carries the folder, the
git rules the skill ships (its .gitignore block is read straight out of SKILL.md, so the
block the agent copies is the block these tests prove), conflict copies, and a git query
that fails: that reads as "not checked", never as zero.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "plugins" / "itakua" / "skills"
CHECK = SKILLS / "itakua-sync" / "scripts" / "check-sync.py"
SYNC_SKILL = SKILLS / "itakua-sync" / "SKILL.md"
NEW_NODE = SKILLS / "itakua-map" / "scripts" / "new-node.sh"
NEW_BRAIN = SKILLS / "itakua-setup" / "scripts" / "new-brain.sh"
REAL_GIT = shutil.which("git")

FAKE_GIT = """#!/bin/sh
# Fail the subcommand named in $FAIL_GIT the way a broken git would; pass the rest on.
for arg in "$@"; do
  case "$arg" in -*) continue ;; esac
  if [ "$arg" = "$FAIL_GIT" ]; then
    echo "fatal: simulated failure" >&2
    exit 128
  fi
  break
done
exec "{real}" "$@"
"""


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30,
                          env={**os.environ, **(env or {})})


def write(path, text="captured\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def gitignore_block():
    """The .gitignore block the sync skill tells an agent to write, as shipped."""
    text = SYNC_SKILL.read_text(encoding="utf-8")
    m = re.search(r"```gitignore\n(.*?)```", text, re.S)
    return "".join(line[2:] + "\n" if line.startswith("  ") else line + "\n"
                   for line in m.group(1).splitlines())


class SyncCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def brain(self, name="brain", *flags):
        brain = Path(self.temp.name) / name
        created = run(["bash", str(NEW_BRAIN), str(brain), "Brain", *flags])
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        made = run(["bash", str(NEW_NODE), "spaces/project"], cwd=brain)
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
        return brain, brain / "spaces" / "project"

    def git_brain(self, declare=True):
        """A brain carried by git the way the skill says: local identity, its block."""
        brain, node = self.brain()
        for cmd in (["git", "init", "-q"],
                    ["git", "config", "--local", "user.name", "Test User"],
                    ["git", "config", "--local", "user.email", "test@example.com"]):
            done = run(cmd, cwd=brain)
            self.assertEqual(done.returncode, 0, done.stderr)
        write(brain / ".gitignore", gitignore_block())
        if declare:
            self.declare(brain, "git", ("Git remote", "none"),
                         ("Git identity", "Test User <test@example.com>"))
        return brain, node

    def declare(self, brain, sync, *rows):
        readme = brain / "README.md"
        text = readme.read_text(encoding="utf-8")
        extra = "".join(f"\n| **{k}** | {v} |" for k, v in rows)
        text = re.sub(r"\| \*\*Sync\*\* \| .*\|", f"| **Sync** | {sync} |{extra}", text)
        readme.write_text(text, encoding="utf-8")

    def commit(self, brain, *paths):
        for cmd in (["git", "add", "--", *map(str, paths)], ["git", "commit", "-qm", "add"]):
            done = run(cmd, cwd=brain)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def check(self, brain, env=None):
        result = run([sys.executable, str(CHECK)], cwd=brain, env=env)
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertIn("sync declared:", result.stdout)
        return result

    @staticmethod
    def lines(result, level):
        return [l.strip()[len(level):].strip() for l in result.stdout.splitlines()
                if l.strip().startswith(level)]

    # --- no sync ----------------------------------------------------------------------

    def test_a_plain_folder_passes_with_nothing_said_about_any_tool(self):
        brain, node = self.brain()
        write(node / "inbox" / "photo.heic")

        result = self.check(brain)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("sync declared: none; found: nothing", result.stdout)
        for word in ("git", "WARN", "PROBLEM", "only on this machine"):
            self.assertNotIn(word, result.stdout)

    def test_deliberate_none_inside_a_synced_folder_is_a_problem(self):
        folder = Path(self.temp.name) / "Dropbox"
        folder.mkdir()
        brain = folder / "work"
        created = run(["bash", str(NEW_BRAIN), str(brain), "Work", "--local-only"])
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        (brain / "spaces").mkdir(exist_ok=True)

        result = self.check(brain)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("sync declared: none, deliberately; found: dropbox", result.stdout)
        self.assertIn("dropbox is in sight", "\n".join(self.lines(result, "PROBLEM")))

    def test_deliberate_none_with_a_git_repository_is_a_problem(self):
        brain, _ = self.brain("work", "--local-only")
        run(["git", "init", "-q"], cwd=brain)

        result = self.check(brain)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("git is in sight", "\n".join(self.lines(result, "PROBLEM")))

    def test_an_undeclared_sync_is_a_note_and_a_declared_missing_git_a_problem(self):
        brain, _ = self.brain()
        run(["git", "init", "-q"], cwd=brain)
        self.assertIn("Sync row does not say so",
                      "\n".join(self.lines(self.check(brain), "note")))

        other, _ = self.brain("other")
        self.declare(other, "git")
        result = self.check(other)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("not a git repository", "\n".join(self.lines(result, "PROBLEM")))

    # --- git ----------------------------------------------------------------------------

    def test_the_skills_block_tracks_inbox_text_and_keeps_the_rest_local(self):
        brain, node = self.git_brain()
        tracked = [write(node / "inbox" / "clip.md"), write(node / "inbox" / "page.html"),
                   write(brain / "00-inbox" / "voice.txt"), write(node / "docs" / "index.md")]
        local = [write(node / "inbox" / "photo.heic"), write(node / "inbox" / "sub" / "a.pdf"),
                 write(brain / "00-inbox" / "scan.png"), write(node / "docs" / "stray.pdf"),
                 write(brain / ".drive-map.local"), write(brain / "status.html")]

        def ignored(path):
            return run(["git", "check-ignore", "-q", str(path)], cwd=brain).returncode == 0

        for path in tracked:
            self.assertFalse(ignored(path), path)
        for path in local:
            self.assertTrue(ignored(path), path)

        result = self.check(brain)

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("WARN", result.stdout)
        self.assertIn("git identity: Test User <test@example.com>", result.stdout)
        only = [l for l in self.lines(result, "note") if "only on this machine" in l]
        self.assertEqual(len(only), 1, result.stdout)
        listed = sorted(only[0].split("): ", 1)[1].split(", "))
        self.assertEqual(listed, ["00-inbox/scan.png", "spaces/project/docs/stray.pdf",
                                  "spaces/project/inbox/photo.heic",
                                  "spaces/project/inbox/sub/a.pdf"])

    def test_a_gitignore_without_the_rules_is_warned_per_rule(self):
        brain, _ = self.git_brain()
        (brain / ".gitignore").write_text("*.pdf\n", encoding="utf-8")

        warns = "\n".join(self.lines(self.check(brain), "WARN"))

        for what in ("inbox binaries", "00-inbox/ binaries", "docs/drive",
                     ".drive-map.local", "status.html"):
            self.assertIn(f"does not keep {what} out of history", warns)

    def test_identity_and_remote_are_compared_with_the_readme(self):
        brain, _ = self.git_brain()
        run(["git", "config", "--local", "user.email", "other@example.com"], cwd=brain)
        run(["git", "remote", "add", "origin", "https://example.com/brain.git"], cwd=brain)

        problems = "\n".join(self.lines(self.check(brain), "PROBLEM"))

        self.assertIn("declares git identity <test@example.com>, the repository is "
                      "configured as <other@example.com>", problems)
        self.assertIn("declares NO git remote, and 1 is configured", problems)

    def test_large_tracked_file_in_a_slot_warns_but_limbo_does_not(self):
        brain, node = self.git_brain()
        big = "x" * (1024 * 1024 + 1)
        in_slot = write(node / "inbox" / "saved-page.html", big)
        in_limbo = write(node / "scratch" / "dump.md", big)
        self.commit(brain, in_slot, in_limbo)

        warns = "\n".join(self.lines(self.check(brain), "WARN"))

        self.assertIn("spaces/project/inbox/saved-page.html is 1.0 MB", warns)
        self.assertNotIn("dump.md", warns)

    def test_a_failed_git_query_is_not_checked_rather_than_zero(self):
        bin_dir = Path(self.temp.name) / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "git"
        fake.write_text(FAKE_GIT.replace("{real}", REAL_GIT), encoding="utf-8")
        fake.chmod(0o755)
        path = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        brain, node = self.git_brain()
        write(node / "inbox" / "photo.heic")
        (brain / ".gitignore").write_text("", encoding="utf-8")
        run(["git", "remote", "add", "origin", "https://example.com/brain.git"], cwd=brain)

        for failing, missing, absent in (
                ("ls-files", "Files only on this machine not checked", "file(s) only on this machine"),
                ("check-ignore", "The .gitignore rule for inbox binaries not checked",
                 "does not keep"),
                ("remote", "Git remote not checked", "NO git remote")):
            result = self.check(brain, env={"PATH": path, "FAIL_GIT": failing})
            warns = "\n".join(self.lines(result, "WARN"))
            self.assertIn(missing, warns, failing)
            self.assertIn("fatal: simulated failure", warns, failing)
            self.assertNotIn(absent, result.stdout, failing)

    # --- other tools ----------------------------------------------------------------------

    def test_syncthing_needs_an_stignore_with_the_three_exclusions(self):
        brain, _ = self.brain()
        self.declare(brain, "syncthing")
        (brain / ".stfolder").mkdir()

        warns = "\n".join(self.lines(self.check(brain), "WARN"))
        self.assertIn("no .stignore at the brain root", warns)

        write(brain / ".stignore", "// itakua\n**/docs/drive\n")
        warns = "\n".join(self.lines(self.check(brain), "WARN"))
        self.assertNotIn("docs/drive", warns)
        self.assertIn("no rule for .drive-map.local", warns)
        self.assertIn("no rule for status.html", warns)

    def test_conflict_copies_are_listed_by_tool(self):
        brain, node = self.brain()
        self.declare(brain, "syncthing, icloud")
        write(brain / ".stignore", "**/docs/drive\n.drive-map.local\nstatus.html\n")
        write(node / "notes" / "plan.md")
        write(node / "notes" / "plan 2.md")
        write(node / "notes" / "plan.sync-conflict-20260101-120000-ABCDEFG.md")
        write(node / "notes" / "plan (Mac's conflicted copy 2026-01-01).md")

        warns = "\n".join(self.lines(self.check(brain), "WARN"))

        self.assertIn("1 syncthing conflict copy: spaces/project/notes/plan.sync-conflict", warns)
        self.assertIn("1 dropbox conflict copy: spaces/project/notes/plan (Mac's", warns)
        self.assertIn("1 icloud conflict copy: spaces/project/notes/plan 2.md", warns)


if __name__ == "__main__":
    unittest.main()
