"""Behavioral regressions for the git/cloud artifact boundary.

These tests intentionally execute the public scripts against small temporary brains.
They assert only user-visible outcomes and filesystem effects so the scripts can keep
evolving internally.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "plugins" / "itakua" / "skills"
MAP_SCRIPTS = SKILLS / "itakua-map" / "scripts"
SETUP_SCRIPTS = SKILLS / "itakua-setup" / "scripts"
VALIDATOR = MAP_SCRIPTS / "check-structure.py"
LINKER = SETUP_SCRIPTS / "link-drive.sh"
NEW_BRAIN = SETUP_SCRIPTS / "new-brain.sh"


class ArtifactLayerBehaviorTests(unittest.TestCase):
    def make_brain(self, parent, *, indexed=False):
        brain = Path(parent) / "brain"
        node = brain / "spaces" / "project"
        for slot in ("notes", "log", "docs"):
            (node / slot).mkdir(parents=True, exist_ok=True)
        (node / "README.md").write_text(
            "# Project\n\n- `notes/`\n- `log/`\n- `docs/`\n",
            encoding="utf-8",
        )
        if indexed:
            (node / "docs" / "index.md").write_text(
                "---\n"
                "type: note\n"
                "---\n\n"
                "# Artifact index\n\n"
                "2 files · 1 KB of real content · updated 2026-09-22\n",
                encoding="utf-8",
            )
        return brain, node

    def run_validator(self, brain):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--no-git"],
            cwd=brain,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def run_linker(self, brain, *args):
        return subprocess.run(
            ["bash", str(LINKER), *map(str, args)],
            cwd=brain,
            capture_output=True,
            text=True,
            timeout=10,
        )

    @staticmethod
    def output(result):
        return (result.stdout + result.stderr).lower()

    def test_validator_rejects_indexed_node_without_drive_link(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, _ = self.make_brain(temp, indexed=True)

            result = self.run_validator(brain)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("docs/drive", self.output(result))
            self.assertIn("absent", self.output(result))
            self.assertIn("2 artifact", self.output(result))

    def test_validator_distinguishes_dangling_drive_link(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp, indexed=True)
            (node / "docs" / "drive").symlink_to(Path(temp) / "not-mounted")

            result = self.run_validator(brain)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("docs/drive", self.output(result))
            self.assertTrue(
                {"dangling", "unavailable"} & set(self.output(result).split()),
                result.stdout + result.stderr,
            )
            self.assertIn("2 artifact", self.output(result))
            self.assertNotIn("docs/drive is absent", self.output(result))

    def test_validator_allows_unused_docs_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, _ = self.make_brain(temp)

            result = self.run_validator(brain)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_linker_uses_committed_portable_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp, indexed=True)
            drive_root = Path(temp) / "drive-root"
            target = drive_root / "shared" / "project-artifacts"
            target.mkdir(parents=True)
            (brain / "drive-map").write_text(
                "project|shared/project-artifacts\n", encoding="utf-8"
            )

            result = self.run_linker(brain, drive_root)

            link = node / "docs" / "drive"
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(link.is_symlink())
            self.assertTrue(os.path.samefile(link, target))

    def test_drive_root_alone_does_not_invent_mapping_for_indexed_node(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp, indexed=True)
            drive_root = Path(temp) / "drive-root"
            drive_root.mkdir()

            result = self.run_linker(brain, drive_root)

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("unmapped", self.output(result))
            self.assertFalse((node / "docs" / "drive").exists())
            self.assertFalse((node / "docs" / "drive").is_symlink())
            self.assertFalse((drive_root / "project").exists())

    def test_linker_rejects_relative_and_nonexistent_drive_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp, indexed=True)
            (brain / "drive-map").write_text("project|mapped\n", encoding="utf-8")
            (brain / "relative-root" / "mapped").mkdir(parents=True)

            relative = self.run_linker(brain, "relative-root")
            missing_root = Path(temp) / "missing-root"
            missing = self.run_linker(brain, missing_root)

            self.assertNotEqual(relative.returncode, 0, relative.stdout + relative.stderr)
            self.assertNotEqual(missing.returncode, 0, missing.stdout + missing.stderr)
            self.assertIn("root", self.output(relative))
            self.assertIn("root", self.output(missing))
            self.assertFalse((node / "docs" / "drive").exists())
            self.assertFalse((node / "docs" / "drive").is_symlink())
            self.assertFalse(missing_root.exists())

    def test_explicit_convention_links_greenfield_node(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp)
            filing = node / "notes" / "topic"
            (filing / "docs").mkdir(parents=True)
            (filing / "README.md").write_text("# A note, not a node\n", encoding="utf-8")
            drive_root = Path(temp) / "drive-root"
            target = drive_root / "project"
            target.mkdir(parents=True)

            result = self.run_linker(brain, "--convention", drive_root)

            link = node / "docs" / "drive"
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(link.is_symlink())
            self.assertTrue(os.path.samefile(link, target))
            self.assertFalse((filing / "docs" / "drive").is_symlink())
            self.assertFalse((drive_root / "project" / "notes" / "topic").exists())

    def test_new_brain_uses_skill_pointers_without_copying_machine_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = Path(temp) / "portable-brain"
            created = subprocess.run(
                [
                    "bash",
                    str(NEW_BRAIN),
                    str(brain),
                    "Portable Brain",
                    "--identity",
                    "Test User <test@example.com>",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )

            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            readme = (brain / "README.md").read_text(encoding="utf-8")
            pointers = "\n".join(
                (brain / name).read_text(encoding="utf-8")
                for name in ("CLAUDE.md", "AGENTS.md")
            )
            self.assertFalse((brain / "skill").exists())
            self.assertNotIn(str(REPO_ROOT), readme)
            self.assertNotIn("plugins/cache", readme)
            self.assertIn("itakua-map", readme)
            self.assertIn("itakua-setup", readme)
            self.assertIn("itakua-setup", pointers)

            rejected = subprocess.run(
                [
                    "bash",
                    str(NEW_BRAIN),
                    str(Path(temp) / "copied-skill-brain"),
                    "Copied Skill Brain",
                    "--with-skill",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("unknown flag", self.output(rejected))


if __name__ == "__main__":
    unittest.main()
