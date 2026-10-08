"""Behavioral regressions for the brain status page, `check-structure.py --report`.

The page is a static snapshot of one validator run: the same findings, plus per-node
inbox, log and machine-local counts. These tests run the public scripts against small
temporary brains and check what a user would: that a plain run writes nothing, that the
page is self-contained, and that its numbers are the text output's.
"""

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "plugins" / "itakua" / "skills"
VALIDATOR = SKILLS / "itakua-map" / "scripts" / "check-structure.py"
NEW_NODE = SKILLS / "itakua-map" / "scripts" / "new-node.sh"
NEW_BRAIN = SKILLS / "itakua-setup" / "scripts" / "new-brain.sh"


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20)


def write(path, text="captured\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def tree(brain):
    """Every path in the brain, to prove a run wrote nothing."""
    return sorted(str(p.relative_to(brain)) for p in brain.rglob("*"))


class StatusPageTests(unittest.TestCase):
    def brain(self, temp):
        brain = Path(temp) / "brain"
        created = run(["bash", str(NEW_BRAIN), str(brain), "Status Brain"])
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        for node in ("spaces/guitar", "spaces/guitar/songs", "spaces/work"):
            made = run(["bash", str(NEW_NODE), node], cwd=brain)
            self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
        return brain

    def populate(self, brain):
        guitar, work = brain / "spaces" / "guitar", brain / "spaces" / "work"
        write(guitar / "inbox" / "tab.md")
        write(guitar / "inbox" / "sub" / "photo.heic")
        write(work / "inbox" / "page.html")
        write(brain / "00-inbox" / "voice.md")
        write(guitar / "log" / "2026-09-01-lesson.md", "---\ndistilled_into: []\n---\n")
        write(guitar / "log" / "2026-09-02-lesson.md", "---\ntype: log\n---\n")
        write(work / "log" / "older" / "2026-08-01-call.md", "---\ntype: log\n---\n")
        write(work / "log" / "2026-09-03-call.md", "---\ntype: log\n---\n")
        write(work / "scratch" / "idea.md")

    def validate(self, brain, *args):
        result = run([sys.executable, str(VALIDATOR), *args], cwd=brain)
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertIn("nodes checked", result.stdout)
        return result

    @staticmethod
    def page(brain):
        return (brain / "status.html").read_text(encoding="utf-8")

    @staticmethod
    def section(page, node):
        # A node is a table row; the brain as a whole is its own block.
        m = re.search(r'<(tr|div) [^>]*data-node="%s".*?</\1>' % re.escape(node),
                      page, re.S)
        return m.group(0) if m else ""

    @staticmethod
    def count(html, name):
        m = re.search(r'data-count="%s">(\d+)<' % name, html)
        return int(m.group(1)) if m else None

    def test_plain_run_writes_nothing_and_report_writes_the_page(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = self.brain(temp)
            self.populate(brain)
            before = tree(brain)

            plain = self.validate(brain)
            self.assertEqual(tree(brain), before)
            self.assertNotIn("status.html", plain.stdout)

            report = self.validate(brain, "--report")
            self.assertEqual(report.returncode, plain.returncode)
            self.assertIn("wrote status.html", report.stdout)
            self.assertEqual(tree(brain), sorted(before + ["status.html"]))

    def test_page_is_self_contained(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = self.brain(temp)
            self.populate(brain)

            self.validate(brain, "--report")

            page = self.page(brain).lower()
            for fetch in ("<script", "<link", "<img", "src=", "url(", "@import", "http"):
                self.assertNotIn(fetch, page)
            self.assertIn("prefers-color-scheme: dark", page)

    def test_page_numbers_match_the_text_output(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = self.brain(temp)
            self.populate(brain)

            result = self.validate(brain, "--report")
            page, text = self.page(brain), result.stdout

            def total(name):
                return int(re.search(r'data-total="%s">(\d+)<' % name, page).group(1))

            lines = [l.strip() for l in text.splitlines()]
            self.assertEqual(total("notes"), sum(l.startswith("note ") for l in lines))
            self.assertEqual(total("warnings"), sum(l.startswith("WARN ") for l in lines))
            self.assertEqual(total("problems"), sum(l.startswith("PROBLEM ") for l in lines))

            inbox = {m.group(1): int(m.group(2))
                     for m in re.finditer(r"note\s+(\S+)/inbox/: (\d+) item", text)}
            logs = {m.group(1): int(m.group(2))
                    for m in re.finditer(r"note\s+(\S+)/log/: (\d+) entr", text)}
            self.assertEqual(inbox, {"spaces/guitar": 2, "spaces/work": 1})
            self.assertEqual(logs, {"spaces/guitar": 1, "spaces/work": 2})
            for node in ("spaces/guitar", "spaces/guitar/songs", "spaces/work"):
                html = self.section(page, node)
                self.assertTrue(html, node)
                self.assertEqual(self.count(html, "inbox"), inbox.get(node, 0), node)
                self.assertEqual(self.count(html, "undistilled"), logs.get(node, 0), node)

            root_inbox = int(re.search(r"note\s+00-inbox/: (\d+) item", text).group(1))
            self.assertEqual(self.count(self.section(page, "(brain)"), "inbox"), root_inbox)
            self.assertEqual(total("inbox"), sum(inbox.values()) + root_inbox)
            self.assertEqual(total("undistilled"), sum(logs.values()))
            self.assertEqual(total("limbo"), text.count("is limbo"))

    def test_brain_derived_text_is_escaped(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = self.brain(temp)
            (brain / "spaces" / "guitar" / "a&b <i>").mkdir()

            self.validate(brain, "--report")

            page = self.page(brain)
            self.assertIn("a&amp;b &lt;i&gt;/ is limbo", page)
            self.assertNotIn("<i>/ is limbo", page)

    def test_the_page_names_no_sync_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = self.brain(temp)
            self.populate(brain)
            (brain / "spaces" / "stray").mkdir()

            result = self.validate(brain, "--report")

            self.assertEqual(result.returncode, 1, result.stdout)
            page = self.page(brain)
            self.assertIn("1 problem(s).", page)
            self.assertIn("spaces/stray/ is neither a slot nor a node", page)
            self.assertNotIn("git", page.lower())

    def test_notes_that_differ_only_by_node_are_folded(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = self.brain(temp)
            for node in ("guitar", "work"):
                write(brain / "spaces" / node / "scratch" / "old.txt")

            result = self.validate(brain, "--report")

            self.assertEqual(result.stdout.count("/scratch/ is limbo"), 2)
            page = self.page(brain)
            self.assertEqual(page.count("/scratch/ is limbo"), 1)
            self.assertIn("2 nodes", page)
            for node in ("spaces/guitar", "spaces/work"):
                self.assertIn(f"<li>{node}</li>", page)

    def test_problems_lead_the_page_and_a_clean_brain_has_no_attention_panel(self):
        with tempfile.TemporaryDirectory() as temp:
            brain = self.brain(temp)

            self.validate(brain, "--report")
            self.assertNotIn("Needs attention", self.page(brain))

            (brain / "spaces" / "stray").mkdir()
            self.validate(brain, "--report")
            page = self.page(brain)
            attention = page.index("Needs attention")
            self.assertLess(attention, page.index("spaces/stray/ is neither a slot nor a node"))
            self.assertLess(attention, page.index("<table"))

if __name__ == "__main__":
    unittest.main()
