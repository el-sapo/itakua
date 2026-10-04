"""Behavioral regressions for the Drive handoff: the README `artifacts:` key and links.

Readers that cannot follow docs/drive (the Reader, agents on the MCP server) find a
node's artifacts through the declared Drive root and the Drive URLs notes carry. These
tests run the public scripts against small temporary brains and assert only what a
user sees: warnings, exit codes, and the generated index.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MAP = REPO_ROOT / "plugins" / "itakua" / "skills" / "itakua-map"
VALIDATOR = MAP / "scripts" / "check-structure.py"
INDEXER = MAP / "scripts" / "index-artifacts.py"
NEW_NODE = MAP / "scripts" / "new-node.sh"

KEY = "artifacts:\n  provider: google-drive\n  root: {root}\n"


def readme(frontmatter=""):
    return (
        "---\ntype: readme\ndomain: project\n" + frontmatter + "---\n\n"
        "# Project\n\n- `notes/`\n- `log/`\n- `docs/`\n"
    )


class DriveRootDeclarationTests(unittest.TestCase):
    def make_brain(self, parent, frontmatter=""):
        brain = Path(parent) / "brain"
        node = brain / "spaces" / "project"
        for slot in ("notes", "log", "docs"):
            (node / slot).mkdir(parents=True, exist_ok=True)
        (node / "README.md").write_text(readme(frontmatter), encoding="utf-8")
        return brain, node

    @staticmethod
    def drive_folder(parent, *parts):
        folder = Path(parent).joinpath("CloudStorage", "GoogleDrive-owner", *parts)
        folder.mkdir(parents=True)
        return folder

    def run_validator(self, brain):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--no-git"],
            cwd=brain, capture_output=True, text=True, timeout=10,
        )
        # A crash prints a traceback and no WARN lines; never let it read as "quiet".
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertIn("nodes checked", result.stdout)
        return result

    @staticmethod
    def warnings(result):
        return [l for l in result.stdout.splitlines() if l.strip().startswith("WARN")]

    def test_linked_node_without_key_is_warned_with_root_from_local_map(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp)
            target = self.drive_folder(temp, "My Drive", "Project Files")
            (node / "docs" / "drive").symlink_to(target)
            (brain / ".drive-map.local").write_text(
                f"# local overrides\nproject|{target}\n", encoding="utf-8")

            result = self.run_validator(brain)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            warned = "\n".join(self.warnings(result))
            self.assertIn("artifacts:", warned)
            self.assertIn(".drive-map.local", warned)
            self.assertIn("root: My Drive/Project Files", warned)
            self.assertNotIn(str(temp), warned)
            self.assertIn("1 warning", result.stdout)

    def test_root_is_proposed_from_link_target_without_local_map(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp)
            target = self.drive_folder(temp, "Shared drives", "Team", "Project")
            (node / "docs" / "drive").symlink_to(target)

            result = self.run_validator(brain)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("root: Shared drives/Team/Project",
                          "\n".join(self.warnings(result)))

    def test_no_root_is_invented_when_mapping_does_not_reach_drive(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp)
            target = Path(temp) / "Dropbox" / "Project"
            target.mkdir(parents=True)
            (node / "docs" / "drive").symlink_to(target)

            result = self.run_validator(brain)

            warned = "\n".join(self.warnings(result))
            self.assertIn("declares no `artifacts:` key", warned)
            self.assertNotIn("propose", warned)
            self.assertNotIn("Dropbox", warned)

    def test_key_without_link_is_warned_without_failing(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, _ = self.make_brain(temp, KEY.format(root="My Drive/Project"))

            result = self.run_validator(brain)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            warned = "\n".join(self.warnings(result))
            self.assertIn("not linked", warned)
            self.assertIn("itakua-setup", warned)

    def test_matching_key_and_link_are_quiet(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp, KEY.format(root="My Drive/Project Files"))
            target = self.drive_folder(temp, "My Drive", "Project Files")
            (node / "docs" / "drive").symlink_to(target)

            result = self.run_validator(brain)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.warnings(result), [], result.stdout)

    def test_decomposed_folder_name_matches_composed_readme(self):
        with tempfile.TemporaryDirectory() as temp:
            composed = unicodedata.normalize("NFC", "Música")
            decomposed = unicodedata.normalize("NFD", "Música")
            brain, node = self.make_brain(temp, KEY.format(root=f"My Drive/{composed}"))
            target = self.drive_folder(temp, "My Drive", decomposed)
            (node / "docs" / "drive").symlink_to(target)

            quiet = self.run_validator(brain)
            (node / "README.md").write_text(readme(), encoding="utf-8")
            proposed = self.run_validator(brain)

            self.assertEqual(quiet.returncode, 0, quiet.stdout)
            self.assertEqual(self.warnings(quiet), [], quiet.stdout)
            self.assertIn(f"root: My Drive/{composed}", "\n".join(self.warnings(proposed)))

    def test_proposed_root_round_trips_for_awkward_folder_names(self):
        for folder in ("Setlist #2", "Clases: 2026", "Notas:", "Fer's Guitar", "Set\tlist"):
            with self.subTest(folder=folder), tempfile.TemporaryDirectory() as temp:
                brain, node = self.make_brain(temp)
                (node / "docs" / "drive").symlink_to(
                    self.drive_folder(temp, "My Drive", folder))

                first = self.run_validator(brain)
                line = re.search(r"`(root: [^`]+)`", "\n".join(self.warnings(first))).group(1)
                frontmatter = f"artifacts:\n  provider: google-drive\n  {line}\n"
                (node / "README.md").write_text(readme(frontmatter), encoding="utf-8")
                second = self.run_validator(brain)

                self.assertEqual(self.warnings(second), [], second.stdout)
                try:
                    import yaml
                except ImportError:
                    continue
                self.assertEqual(yaml.safe_load(frontmatter)["artifacts"]["root"],
                                 f"My Drive/{folder}")

    def test_stale_key_is_warned_with_the_mapped_root(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp, KEY.format(root="My Drive/Old"))
            target = self.drive_folder(temp, "My Drive", "New")
            (node / "docs" / "drive").symlink_to(target)

            result = self.run_validator(brain)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            warned = "\n".join(self.warnings(result))
            self.assertIn("My Drive/Old", warned)
            self.assertIn("My Drive/New", warned)

    def test_dangling_link_still_counts_as_linked(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp, KEY.format(root="My Drive/Project"))
            gone = Path(temp) / "CloudStorage" / "GoogleDrive-owner" / "My Drive" / "Project"
            (node / "docs" / "drive").symlink_to(gone)

            result = self.run_validator(brain)

            self.assertIn("dangling", result.stdout.lower())
            self.assertEqual(self.warnings(result), [], result.stdout)

    def test_unreadable_or_placeholder_keys_are_warned(self):
        cases = {
            "artifacts: {provider: google-drive, root: My Drive/Project}\n": "no readable `root`",
            KEY.format(root="My Drive/<folder>"): "placeholder",
            "artifacts:\n  provider: gdrive\n  root: My Drive/Project\n": "gdrive",
            "artifacts:\n  provider: google-drive\n  root: My Drive/A: B\n": "no readable `root`",
            "artifacts:\n\tprovider: google-drive\n\troot: My Drive/Project\n": "no readable `root`",
            "artifacts:\n  provider: google-drive\n  \troot: My Drive/Project\n": "no readable `root`",
            # A lone surrogate escape must be reported, not crash the printed warning.
            'artifacts:\n  provider: "\\ud800"\n  root: "My Drive/\\udfff"\n': "no readable `root`",
        }
        for frontmatter, expected in cases.items():
            with self.subTest(frontmatter=frontmatter), tempfile.TemporaryDirectory() as temp:
                brain, node = self.make_brain(temp, frontmatter)
                (node / "docs" / "drive").symlink_to(
                    self.drive_folder(temp, "My Drive", "Project"))

                result = self.run_validator(brain)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(expected, "\n".join(self.warnings(result)))

    def test_new_node_carries_the_key_commented_and_validates_quietly(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = Path(temp) / "brain"
            (brain / "spaces").mkdir(parents=True)

            created = subprocess.run(
                ["bash", str(NEW_NODE), "spaces/project"],
                cwd=brain, capture_output=True, text=True, timeout=10,
            )
            result = self.run_validator(brain)

            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.assertIn("artifacts:", created.stdout)
            text = (brain / "spaces" / "project" / "README.md").read_text(encoding="utf-8")
            frontmatter = text.split("---")[1]
            self.assertIn("# artifacts:", frontmatter)
            self.assertIn("#   provider: google-drive", frontmatter)
            self.assertIn("#   root: My Drive/", frontmatter)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.warnings(result), [], result.stdout)


    def test_template_key_uncommented_in_place_is_read(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = Path(temp) / "brain"
            (brain / "spaces").mkdir(parents=True)
            subprocess.run(["bash", str(NEW_NODE), "spaces/project"], cwd=brain,
                           capture_output=True, check=True, timeout=10)
            path = brain / "spaces" / "project" / "README.md"
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            # Uncomment exactly as a person would: drop "# ", keep the trailing comments.
            lines = [l[2:].replace("<folder>", "Project") if l.startswith(("# artifacts:", "#   "))
                     else l for l in lines]
            path.write_text("".join(lines), encoding="utf-8")
            (path.parent / "docs").mkdir()
            (path.parent / "docs" / "drive").symlink_to(
                self.drive_folder(temp, "My Drive", "Project"))

            result = self.run_validator(brain)

            self.assertIn("  root: My Drive/Project   #", path.read_text(encoding="utf-8"))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.warnings(result), [], result.stdout)


class IndexLinkColumnTests(unittest.TestCase):
    DOC_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789-_"
    SHEET_ID = "1ZyXwVuTsRqPoNmLkJiHgFeDcBa98765"
    LEGACY_ID = "1LeGaCyBaCkUpAnDsYnC0123456789"

    def build(self, temp):
        node = Path(temp) / "brain" / "spaces" / "project"
        drive = Path(temp) / "drive"
        for d in (node / "notes", node / "log", node / "docs", drive / "songs"):
            d.mkdir(parents=True, exist_ok=True)
        (node / "README.md").write_text(readme(), encoding="utf-8")
        (node / "docs" / "drive").symlink_to(drive)

        def pointer(path, file_id, key=""):
            path.write_text(json.dumps({
                "": "WARNING! DO NOT EDIT THIS FILE! ANY CHANGES MADE WILL BE LOST!",
                "doc_id": file_id, "resource_key": key, "email": "owner@example.com",
            }), encoding="utf-8")

        pointer(drive / "songs" / "Song.gdoc", self.DOC_ID)
        pointer(drive / "Inventory.gsheet", self.SHEET_ID, key="0-AbC_123")
        (drive / "Deck.gslides").write_text("not json", encoding="utf-8")
        (drive / "Legacy.gdoc").write_text(json.dumps(
            {"resource_id": f"document:{self.LEGACY_ID}", "email": "owner@example.com"}),
            encoding="utf-8")
        pointer(drive / "Odd.gsheet", "../x y")
        pointer(drive / "BadKey.gslides", self.SHEET_ID, key="0&x=<script>")
        (drive / "Array.gdoc").write_text("[]", encoding="utf-8")
        (drive / "Deep.gdoc").write_text("[" * 5000, encoding="utf-8")
        if hasattr(os, "mkfifo"):
            os.mkfifo(drive / "Pipe.gdoc")
        (drive / "songs" / "Tab.docx").write_bytes(b"PK\x03\x04 binary")
        (node / "docs" / "pointers-ok.md").write_text(
            "- `songs/Song.gdoc`\n", encoding="utf-8")
        return node

    def run_indexer(self, node, lang):
        brain = node.parents[1]
        result = subprocess.run(
            [sys.executable, str(INDEXER), "spaces/project", "--lang", lang],
            cwd=brain, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result, (node / "docs" / "index.md").read_text(encoding="utf-8")

    @staticmethod
    def row(index, name):
        rows = [l for l in index.splitlines() if l.startswith(f"| `{name}`")]
        assert len(rows) == 1, (name, index)
        return [c.strip() for c in rows[0].strip().strip("|").split("|")]

    def test_pointer_files_get_drive_urls_and_other_files_stay_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)

            result, index = self.run_indexer(node, "en")

            self.assertIn("| File | Type | Size | Link |", index)
            self.assertIn("| File | Kind | Link |", index)
            song = self.row(index, "songs/Song.gdoc")
            self.assertEqual(song[-1], f"<https://drive.google.com/open?id={self.DOC_ID}>")
            sheet = self.row(index, "Inventory.gsheet")
            self.assertEqual(
                sheet[-1],
                f"<https://drive.google.com/open?id={self.SHEET_ID}&resourcekey=0-AbC_123>")
            self.assertEqual(self.row(index, "Legacy.gdoc")[-1],
                             f"<https://drive.google.com/open?id={self.LEGACY_ID}>")
            self.assertEqual(self.row(index, "BadKey.gslides")[-1],
                             f"<https://drive.google.com/open?id={self.SHEET_ID}>")
            for unreadable in ("Deck.gslides", "Odd.gsheet", "Array.gdoc", "Deep.gdoc"):
                self.assertEqual(self.row(index, unreadable)[-1], "", unreadable)
            if hasattr(os, "mkfifo"):
                self.assertEqual(self.row(index, "Pipe.gdoc")[-1], "")
            tab = self.row(index, "Tab.docx")
            self.assertEqual(len(tab), 4)
            self.assertEqual(tab[-1], "")
            self.assertNotIn("owner@example.com", index)
            self.assertIn("4 Drive link(s)", result.stdout)
            self.assertIn("had no readable Drive id", result.stdout)

    def test_accepted_pointers_are_listed_with_their_links(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)

            _, index = self.run_indexer(node, "es")

            accepted = index.split("## Punteros aceptados (1)")[1]
            self.assertIn("| Archivo | Tipo | Enlace |", accepted)
            self.assertIn(f"open?id={self.DOC_ID}", accepted)
            self.assertIn("| Archivo | Tipo | Tamaño | Enlace |", index)
            self.assertRegex(index, r"(?m)^\d+ archivos ·")


if __name__ == "__main__":
    unittest.main()
