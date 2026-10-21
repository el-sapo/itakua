"""Behavioral regressions for a node README's `## Contracts` table.

A row lets an agent work on one slot (or a folder inside it) without asking; no row means
manual. The validator only checks that a row can mean something: its slot is one of the
four and exists in the node, and its mode is one it knows. It also warns on a README long
enough to stop being read. These tests run the public scripts against small temporary
brains and assert only what a user sees: output lines and exit codes.
"""

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

GUITAR_ROW = ("| `inbox/clases/` | notify | distil to `log/` and `notes/`, mark the item "
              "distilled | reads the report; asks for amendments or a revert; removal "
              "still asks |")


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20,
                          env=dict(os.environ))


class ContractsTests(unittest.TestCase):
    def brain(self, temp):
        brain = Path(temp) / "brain"
        (brain / "spaces").mkdir(parents=True)
        created = run(["bash", str(NEW_NODE), "spaces/guitar"], cwd=brain)
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        return brain, brain / "spaces" / "guitar"

    def validate(self, brain):
        result = run([sys.executable, str(VALIDATOR)], cwd=brain)
        # A crash prints a traceback and no findings; never let it read as "quiet".
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertIn("nodes checked", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result

    @staticmethod
    def warns(result):
        return [l.strip()[len("WARN"):].strip() for l in result.stdout.splitlines()
                if l.strip().startswith("WARN")]

    @staticmethod
    def add_rows(node, *rows):
        readme = node / "README.md"
        text = readme.read_text(encoding="utf-8")
        header = "| Slot | Mode | Agent does | Owner does |\n|------|------|------------|------------|\n"
        assert header in text, "the template's Contracts header changed"
        readme.write_text(text.replace(header, header + "".join(r + "\n" for r in rows)),
                          encoding="utf-8")

    def test_a_new_node_has_an_empty_contracts_table_and_no_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            text = (node / "README.md").read_text(encoding="utf-8")
            section = text.split("## Contracts", 1)[1].split("\n## ", 1)[0]
            rows = [l for l in section.splitlines() if l.startswith("|")]
            self.assertEqual(rows[0], "| Slot | Mode | Agent does | Owner does |")
            self.assertEqual(len(rows), 2, "the template ships the header row only")
            self.assertNotIn("follows the default contract", text)
            self.assertEqual(self.warns(self.validate(brain)), [])

    def test_a_readme_without_contracts_is_not_warned(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            readme = node / "README.md"
            text = readme.read_text(encoding="utf-8")
            start = text.index("## Contracts")
            end = text.index("\n## ", start + 1)
            readme.write_text(text[:start] + text[end + 1:], encoding="utf-8")
            self.assertEqual(self.warns(self.validate(brain)), [])

    def test_a_row_for_an_existing_subfolder_is_quiet(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            (node / "inbox" / "clases").mkdir()
            self.add_rows(node, GUITAR_ROW)
            self.assertEqual(self.warns(self.validate(brain)), [])

    def test_a_row_for_a_missing_folder_is_warned(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            self.add_rows(node, GUITAR_ROW)
            warns = self.warns(self.validate(brain))
            self.assertEqual(len(warns), 1, warns)
            self.assertIn("README.md", warns[0])
            self.assertIn("inbox/clases/", warns[0])
            self.assertIn("does not exist", warns[0])

    def test_a_row_for_a_folder_that_is_not_a_slot_is_warned(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            (node / "notas").mkdir()
            self.add_rows(node, "| `notas/` | notify | distil | reads the report |")
            warns = self.warns(self.validate(brain))
            self.assertEqual(len(warns), 1, warns)
            self.assertIn("notas/", warns[0])
            self.assertIn("not a slot", warns[0])

    def test_an_unknown_mode_is_warned(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            self.add_rows(node, "| `log/` | notfy | append | reads the report |")
            warns = self.warns(self.validate(brain))
            self.assertEqual(len(warns), 1, warns)
            self.assertIn("notfy", warns[0])
            self.assertIn("mode", warns[0])

    def test_a_manual_row_is_quiet(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            self.add_rows(node, "| `inbox/` | manual | only on request | asks |")
            self.assertEqual(self.warns(self.validate(brain)), [])

    def pad_body(self, node, lines):
        """Pad the README so its body, front matter excluded, is exactly `lines` long."""
        readme = node / "README.md"
        text = readme.read_text(encoding="utf-8")
        end = text.index("\n---\n", 4) + len("\n---\n")
        body = text[end:].splitlines()
        self.assertLess(len(body), lines, "the template body is already this long")
        body += ["- filler"] * (lines - len(body))
        readme.write_text(text[:end] + "\n".join(body) + "\n", encoding="utf-8")

    def test_a_readme_body_over_120_lines_is_warned(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            self.pad_body(node, 121)
            warns = self.warns(self.validate(brain))
            self.assertEqual(len(warns), 1, warns)
            self.assertIn("121 lines", warns[0])

    def test_a_readme_body_of_120_lines_is_quiet(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.brain(temp)
            self.pad_body(node, 120)
            self.assertEqual(self.warns(self.validate(brain)), [])


if __name__ == "__main__":
    unittest.main()
