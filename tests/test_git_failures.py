"""Behavioral regressions for a git query that fails: it is "not checked", never zero.

The validator asks git which files exist only on this machine, which tracked files are
large, when inbox items were added, what the remote is, and what is ignored. A failed or
timed-out call used to read as an empty answer -- "0 files only on this machine", no size
warning, no remote -- which is an all-clear nobody earned. These tests put a fake `git`
first on PATH that fails one subcommand and passes every other call to the real git.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "plugins" / "itakua" / "skills"
VALIDATOR = SKILLS / "itakua-map" / "scripts" / "check-structure.py"
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


class FailedGitQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        bin_dir = Path(self.temp.name) / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "git"
        fake.write_text(FAKE_GIT.replace("{real}", REAL_GIT), encoding="utf-8")
        fake.chmod(0o755)
        self.path = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"

    def brain(self, *flags):
        brain = Path(self.temp.name) / "brain"
        created = run(["bash", str(NEW_BRAIN), str(brain), "Brain",
                       "--identity", "Test User <test@example.com>", *flags])
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        made = run(["bash", str(NEW_NODE), "spaces/project"], cwd=brain)
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
        return brain, brain / "spaces" / "project"

    def commit(self, brain, *paths):
        for cmd in (["git", "add", "--", *map(str, paths)], ["git", "commit", "-qm", "add"]):
            done = run(cmd, cwd=brain)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def validate(self, brain, failing, *args):
        result = run([sys.executable, str(VALIDATOR), "--report", *args], cwd=brain,
                     env={"PATH": self.path, "FAIL_GIT": failing})
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertIn("nodes checked", result.stdout)
        page = (brain / "status.html").read_text(encoding="utf-8")
        return result.stdout, page

    @staticmethod
    def warns(text):
        return "\n".join(l for l in text.splitlines() if l.strip().startswith("WARN"))

    def test_failed_ls_files_is_not_checked_rather_than_zero(self):
        brain, node = self.brain()
        write(node / "inbox" / "photo.heic")
        big = write(node / "notes" / "huge.md", "x" * (1024 * 1024 + 1))
        self.commit(brain, big)

        text, page = self.validate(brain, "ls-files")

        warns = self.warns(text)
        self.assertIn("Files only on this machine not checked: `git ls-files` failed "
                      "(fatal: simulated failure)", warns)
        self.assertIn("Tracked files over 1 MB not checked", warns)
        self.assertNotIn("only on this machine (ignored by git", text)
        self.assertNotIn('data-count="local"', page)
        self.assertIn("not checked: git failed", page)
        self.assertIn("Files only on this machine · not checked", page)

    def test_failed_log_leaves_counts_but_ages_not_checked(self):
        brain, node = self.brain()
        self.commit(brain, write(node / "inbox" / "clip.md"))

        text, page = self.validate(brain, "log")

        self.assertIn("spaces/project/inbox/: 1 item(s), oldest not checked", text)
        self.assertIn("Inbox ages not checked: `git log` failed", self.warns(text))
        self.assertIn('data-count="inbox">1<', page)
        self.assertIn("oldest not checked: git failed", page)
        self.assertIn("Days the oldest has waited · not checked", page)

    def test_failed_check_ignore_is_not_a_false_alarm(self):
        brain, _ = self.brain()
        # Neither the allowlist nor status.html is ignored, so a working git would warn
        # about both. A failing one must say it could not check, not that they are wrong.
        (brain / ".gitignore").write_text("_tmp/\n", encoding="utf-8")

        text, _ = self.validate(brain, "check-ignore")

        warns = self.warns(text)
        self.assertIn("The inbox/ allowlist not checked: `git check-ignore` failed", warns)
        self.assertIn("The 00-inbox/ allowlist not checked", warns)
        self.assertIn("The status.html ignore rule not checked", warns)
        self.assertNotIn("would commit binaries", warns)
        self.assertNotIn("status.html is not gitignored", warns)

    def test_failed_remote_is_not_read_as_no_remote(self):
        brain, _ = self.brain("--local-only")
        run(["git", "remote", "add", "origin", "https://example.com/brain.git"], cwd=brain)

        working, _ = self.validate(brain, "none")
        text, page = self.validate(brain, "remote")

        self.assertIn("README declares NO REMOTE", working)
        self.assertIn("Git remote not checked: `git remote` failed", self.warns(text))
        self.assertNotIn("no remote configured", text)
        self.assertIn("<dt>Git remote</dt><dd>not checked</dd>", page)


if __name__ == "__main__":
    unittest.main()
