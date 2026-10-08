"""Behavioral regressions for the inbox/ slot, limbo, and what git says about the tree.

inbox/ is the fourth slot: text there is tracked, every other file stays on the machine, and any folder inside a node that is neither a slot nor a
child node is limbo -- a note, never a failure. These tests run the public scripts against
small temporary brains and assert only what a user sees: ignore rules, output lines and
exit codes.
"""

import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "plugins" / "itakua" / "skills"
VALIDATOR = SKILLS / "itakua-map" / "scripts" / "check-structure.py"
NEW_NODE = SKILLS / "itakua-map" / "scripts" / "new-node.sh"
NEW_BRAIN = SKILLS / "itakua-setup" / "scripts" / "new-brain.sh"


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20,
                          env={**os.environ, **(env or {})})


class InboxSlotTests(unittest.TestCase):
    def plain_brain(self, temp):
        """A brain outside git, with one node scaffolded the supported way."""
        brain = Path(temp) / "brain"
        (brain / "spaces").mkdir(parents=True)
        self.new_node(brain, "spaces/project")
        return brain, brain / "spaces" / "project"

    def git_brain(self, temp):
        """A fresh brain from new-brain.sh, with its own identity and one node."""
        brain = Path(temp) / "brain"
        created = run(["bash", str(NEW_BRAIN), str(brain), "Test Brain",
                       "--identity", "Test User <test@example.com>"])
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        self.new_node(brain, "spaces/project")
        return brain, brain / "spaces" / "project"

    def new_node(self, brain, path):
        created = run(["bash", str(NEW_NODE), path], cwd=brain)
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)

    def validate(self, brain, *args):
        result = run([sys.executable, str(VALIDATOR), *args], cwd=brain)
        # A crash prints a traceback and no findings; never let it read as "quiet".
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertIn("nodes checked", result.stdout)
        return result

    @staticmethod
    def lines(result, level):
        return [l.strip()[len(level):].strip() for l in result.stdout.splitlines()
                if l.strip().startswith(level)]

    @staticmethod
    def write(path, text="captured\n"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, brain, *paths, date=None):
        env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else None
        added = run(["git", "add", "--", *map(str, paths)], cwd=brain)
        self.assertEqual(added.returncode, 0, added.stderr)
        done = run(["git", "commit", "-qm", "capture"], cwd=brain, env=env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    # --- scaffolding ----------------------------------------------------------------

    def test_new_node_creates_inbox(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.plain_brain(temp)

            result = self.validate(brain, "--no-git")

            self.assertTrue((node / "inbox" / ".gitkeep").is_file())
            readme = (node / "README.md").read_text(encoding="utf-8")
            self.assertIn("`inbox/`", readme)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.lines(result, "WARN"), [], result.stdout)
            self.assertEqual(self.lines(result, "PROBLEM"), [], result.stdout)

    def test_fresh_brain_tracks_inbox_text_and_keeps_binaries_local(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.git_brain(temp)
            tracked = ["inbox/clip.md", "inbox/page.html", "inbox/sub/dictated.txt"]
            local = ["inbox/photo.heic", "inbox/scan.pdf", "inbox/sub/book.epub"]
            for rel in tracked + local:
                self.write(node / rel)
            root_tracked, root_local = brain / "00-inbox" / "n.md", brain / "00-inbox" / "p.heic"
            self.write(root_tracked)
            self.write(root_local)

            def ignored(path):
                return run(["git", "check-ignore", "-q", str(path)], cwd=brain).returncode == 0

            for rel in tracked:
                self.assertFalse(ignored(node / rel), rel)
            for rel in local:
                self.assertTrue(ignored(node / rel), rel)
            self.assertFalse(ignored(root_tracked))
            self.assertTrue(ignored(root_local))

    # --- limbo ----------------------------------------------------------------------

    def test_limbo_is_a_note_and_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.plain_brain(temp)
            self.write(node / "scratch" / "deeper" / "idea.md")

            result = self.validate(brain, "--no-git")

            notes = "\n".join(self.lines(result, "note"))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("spaces/project/scratch/ is limbo", notes)
            self.assertNotIn("scratch/deeper", result.stdout)
            self.assertEqual(self.lines(result, "PROBLEM"), [], result.stdout)

    def test_readme_inside_limbo_is_warned(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.plain_brain(temp)
            self.write(node / "clients" / "acme" / "README.md", "# Acme\n")

            result = self.validate(brain, "--no-git")

            warns = "\n".join(self.lines(result, "WARN"))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("spaces/project/clients/acme/ has a README.md", warns)
            self.assertIn("inside limbo spaces/project/clients/", warns)

    def test_folder_without_readme_directly_under_spaces_still_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, _ = self.plain_brain(temp)
            self.write(brain / "spaces" / "scratch" / "idea.md")

            result = self.validate(brain, "--no-git")

            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("spaces/scratch/", "\n".join(self.lines(result, "PROBLEM")))

    # --- inbox counts ---------------------------------------------------------------

    def test_inbox_count_and_oldest_item(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.plain_brain(temp)
            self.write(node / "inbox" / "clip.md")
            self.write(node / "inbox" / "sub" / "new.txt")
            self.write(node / "inbox" / ".DS_Store")

            result = self.validate(brain, "--no-git")

            today = datetime.date.today().isoformat()
            self.assertIn(f"spaces/project/inbox/: 2 item(s), oldest {today} (0 day(s))",
                          "\n".join(self.lines(result, "note")))

    def test_an_old_file_dropped_in_today_has_waited_since_today(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.plain_brain(temp)
            pdf = self.write(node / "inbox" / "statement-2019.pdf")
            stamp = datetime.datetime(2019, 3, 2, 12).timestamp()
            os.utime(pdf, (stamp, stamp))          # modified in 2019, arrived now

            result = self.validate(brain, "--no-git")

            today = datetime.date.today().isoformat()
            self.assertIn(f"inbox/: 1 item(s), oldest {today} (0 day(s))", result.stdout)
            self.assertNotIn("2019", result.stdout.replace("statement-2019", ""))

    def test_empty_inbox_prints_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, _ = self.plain_brain(temp)

            result = self.validate(brain, "--no-git")

            self.assertNotIn("inbox/:", result.stdout)

    def test_root_inbox_captures_and_plain_drops_are_items_without_warnings(self):
        # The capture format is loose: a capture, a broken header and a plain drop are all
        # just items, counted the same and never warned about. A distilled line changes
        # nothing either.
        with tempfile.TemporaryDirectory() as temp:
            brain, _ = self.plain_brain(temp)
            before = self.validate(brain, "--no-git")
            root = brain / "00-inbox"
            self.write(root / "2026-10-06-clase-12.md",
                       "---\ntype: capture\nsource: dictalo\nkind: transcript\n"
                       "title: \"Clase 12: tríadas\"\n"
                       "captured_at: 2026-10-06T19:42:11-03:00\n---\n\n"
                       "Distilled 2026-10-08 into spaces/project/log/2026-10-08-clase-12.md\n\n"
                       "## Note\nRepasar la tríada mayor.\n")
            self.write(root / "broken.md",
                       "---\ntype: capture\ntitle: Clase 12: tríadas\n\n## Note\nno closing line\n")
            self.write(root / "thought.md", "just a thought\n")

            result = self.validate(brain, "--no-git")

            self.assertEqual(result.returncode, before.returncode, result.stdout)
            self.assertEqual(self.lines(result, "WARN"), self.lines(before, "WARN"))
            self.assertEqual(self.lines(result, "PROBLEM"), self.lines(before, "PROBLEM"))
            self.assertIn("00-inbox/: 3 item(s)", result.stdout)

    def test_oldest_item_survives_a_fresh_checkout_through_git(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.git_brain(temp)
            clip = self.write(node / "inbox" / "clip.md")
            self.commit(brain, clip, date="2026-02-03T12:00:00")
            os.utime(clip)                         # resets ctime, as a fresh clone does

            with_git = self.validate(brain)
            without = self.validate(brain, "--no-git")

            self.assertIn("inbox/: 1 item(s), oldest 2026-02-03", with_git.stdout)
            self.assertNotIn("oldest 2026-02-03", without.stdout)

    # --- what git says --------------------------------------------------------------

    def test_files_only_on_this_machine_are_listed(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.git_brain(temp)
            self.write(node / "inbox" / "photo.heic")
            self.write(node / "inbox" / "clip.md")
            self.write(node / "inbox" / ".DS_Store")
            self.write(node / "docs" / "stray.pdf")
            cloud = Path(temp) / "cloud"
            cloud.mkdir()
            (node / "docs" / "drive").symlink_to(cloud)

            result = self.validate(brain)

            local = [l for l in self.lines(result, "note") if "only on this machine" in l]
            self.assertEqual(len(local), 1, result.stdout)
            self.assertIn("spaces/project/: 2 file(s) only on this machine", local[0])
            listed = local[0].split("): ", 1)[1].split(", ")
            self.assertEqual(sorted(listed), ["docs/stray.pdf", "inbox/photo.heic"])

    def test_large_tracked_file_in_a_slot_warns_but_limbo_does_not(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.git_brain(temp)
            big = "x" * (1024 * 1024 + 1)
            in_slot = self.write(node / "inbox" / "saved-page.html", big)
            in_limbo = self.write(node / "scratch" / "dump.md", big)
            self.commit(brain, in_slot, in_limbo)

            result = self.validate(brain)

            warns = "\n".join(self.lines(result, "WARN"))
            self.assertIn("spaces/project/inbox/saved-page.html is 1.0 MB", warns)
            self.assertNotIn("dump.md", warns)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_gitignore_without_the_inbox_allowlist_is_warned(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, _ = self.plain_brain(temp)
            (brain / ".gitignore").write_text("*.pdf\n", encoding="utf-8")
            for cmd in (["git", "init", "-q"],
                        ["git", "config", "--local", "user.name", "Test User"],
                        ["git", "config", "--local", "user.email", "test@example.com"]):
                run(cmd, cwd=brain)

            result = self.validate(brain)

            self.assertIn(".gitignore would commit binaries dropped in inbox/",
                          "\n".join(self.lines(result, "WARN")))

    def test_scaffolded_brain_has_the_allowlist(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, _ = self.git_brain(temp)

            result = self.validate(brain)

            self.assertNotIn(".gitignore would commit", result.stdout)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_no_git_makes_no_git_findings(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.git_brain(temp)
            self.write(node / "inbox" / "photo.heic")
            big = self.write(node / "notes" / "huge.md", "x" * (1024 * 1024 + 1))
            self.commit(brain, big)
            (brain / ".gitignore").write_text("", encoding="utf-8")

            result = self.validate(brain, "--no-git")

            for git_only in ("only on this machine", "MB and tracked", ".gitignore would"):
                self.assertNotIn(git_only, result.stdout)


if __name__ == "__main__":
    unittest.main()
