"""Behavioral regressions for the Drive handoff: the README `artifacts:` key and links.

Readers that cannot follow docs/drive (the Reader, agents on the MCP server) find a
node's artifacts through the declared Drive root and link, and the Drive URLs notes carry.
These tests run the public scripts against small temporary brains and assert only what a
user sees: warnings, exit codes, and the generated index.

Drive ids are read on macOS with Apple's `xattr`. Every run here gets an explicit PATH:
either none with an `xattr` on it, or a fake one first, answering from a map the test
writes. Nothing depends on whether the machine running the tests has the real command.
"""

import json
import os
from pathlib import Path
import re
import shlex
import shutil
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
# The indexer's limit, read from the script: a folder with more files is summarised.
COLLAPSE_OVER = int(re.search(r"(?m)^COLLAPSE_OVER = (\d+)$",
                              INDEXER.read_text(encoding="utf-8")).group(1))

KEY = "artifacts:\n  provider: google-drive\n  root: {root}\n"
URL_KEY = KEY + "  url: {url}\n"
FOLDERS = "https://drive.google.com/drive/folders/"

FAKE_XATTR = """\
import json, os, sys, time
# A stand-in for Apple's xattr. `xattr -p <name> <path>` answers from the JSON file named
# by FAKE_XATTR_ANSWERS, keyed by real path: a string is printed, an object gives its own
# stdout and exit status, after `sleep` seconds if it says so. A path that is not already
# resolved fails, as a missing one does. Every path asked about is logged beside the answers.
args = sys.argv[1:]
with open(os.environ["FAKE_XATTR_ANSWERS"], encoding="utf-8") as f:
    answers = json.load(f)
with open(os.environ["FAKE_XATTR_ANSWERS"] + ".log", "a", encoding="utf-8") as log:
    log.write(args[-1] + "\\n" if args else "\\n")
answer = None
if len(args) == 3 and args[:2] == ["-p", "com.google.drivefs.item-id#S"] \\
        and args[2] == os.path.realpath(args[2]):
    answer = answers.get(args[2])
if isinstance(answer, str):
    answer = {"stdout": answer + "\\n", "exit": 0}
if answer is None:
    sys.stderr.write("xattr: No such xattr: com.google.drivefs.item-id#S\\n")
    sys.exit(1)
time.sleep(answer.get("sleep", 0))
sys.stdout.write(answer["stdout"])
sys.exit(answer["exit"])
"""


def no_xattr_env():
    """The environment with a PATH that has no `xattr` on it."""
    dirs = [d for d in (os.path.dirname(sys.executable), "/usr/bin", "/bin")
            if not shutil.which("xattr", path=d)]
    env = {k: v for k, v in os.environ.items() if k != "FAKE_XATTR_ANSWERS"}
    env["PATH"] = os.pathsep.join(dirs)
    return env


def fake_xattr_env(temp, answers):
    """The environment with a fake `xattr` first on PATH, answering `answers` by path."""
    bin_dir = Path(temp) / "fake-bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "fake_xattr.py").write_text(FAKE_XATTR, encoding="utf-8")
    wrapper = bin_dir / "xattr"
    wrapper.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} "
                       f"{shlex.quote(str(bin_dir / 'fake_xattr.py'))} \"$@\"\n",
                       encoding="utf-8")
    wrapper.chmod(0o755)
    table = Path(temp) / "xattr-answers.json"
    table.write_text(json.dumps({os.path.realpath(k): v for k, v in answers.items()}),
                     encoding="utf-8")
    env = no_xattr_env()
    env["PATH"] = os.pathsep.join([str(bin_dir), env["PATH"]])
    env["FAKE_XATTR_ANSWERS"] = str(table)
    return env


def readme(frontmatter=""):
    return (
        "---\ntype: readme\ndomain: project\n" + frontmatter + "---\n\n"
        "# Project\n\n- `notes/`\n- `log/`\n- `docs/`\n"
    )


class BrainMixin:
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

    def run_validator(self, brain, env=None):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "--no-git"],
            cwd=brain, capture_output=True, text=True, timeout=20,
            env=env or no_xattr_env(),
        )
        # A crash prints a traceback and no WARN lines; never let it read as "quiet".
        self.assertEqual(result.stderr, "", result.stderr)
        self.assertIn("nodes checked", result.stdout)
        return result

    @staticmethod
    def warnings(result):
        return [l for l in result.stdout.splitlines() if l.strip().startswith("WARN")]

    @staticmethod
    def notes(result):
        return [l for l in result.stdout.splitlines() if l.strip().startswith("note")]


class DriveRootDeclarationTests(BrainMixin, unittest.TestCase):
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
            self.assertIn(f"#   url: {FOLDERS}", frontmatter)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.warnings(result), [], result.stdout)


    def test_template_key_uncommented_in_place_is_read(self):
        folder_id = "1TeMpLaTeFoLdEr0123456789"
        with tempfile.TemporaryDirectory() as temp:
            brain = Path(temp) / "brain"
            (brain / "spaces").mkdir(parents=True)
            subprocess.run(["bash", str(NEW_NODE), "spaces/project"], cwd=brain,
                           capture_output=True, check=True, timeout=10)
            path = brain / "spaces" / "project" / "README.md"
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            # Uncomment exactly as a person would: drop "# ", keep the trailing comments.
            lines = [l[2:].replace("<folder>", "Project").replace("<folder id>", folder_id)
                     if l.startswith(("# artifacts:", "#   ")) else l for l in lines]
            path.write_text("".join(lines), encoding="utf-8")
            (path.parent / "docs").mkdir()
            target = self.drive_folder(temp, "My Drive", "Project")
            (path.parent / "docs" / "drive").symlink_to(target)

            result = self.run_validator(brain, fake_xattr_env(temp, {target: folder_id}))

            text = path.read_text(encoding="utf-8")
            self.assertIn("  root: My Drive/Project   #", text)
            self.assertIn(f"  url: {FOLDERS}{folder_id}\n", text)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.warnings(result), [], result.stdout)
            try:
                import yaml
            except ImportError:
                return
            declared = yaml.safe_load(text.split("---")[1])["artifacts"]
            self.assertEqual(declared["url"], f"{FOLDERS}{folder_id}")


class DriveFolderUrlTests(BrainMixin, unittest.TestCase):
    """`artifacts.url`: proposed and compared only where the folder's Drive id is readable."""

    FOLDER_ID = "1FoLdErAbCdEfGhIjKlMnOpQrStUv"
    OTHER_ID = "1OtHeRfOlDeRzYxWvUtSrQpOnMlK"

    def linked(self, temp, frontmatter=""):
        brain, node = self.make_brain(temp, frontmatter)
        target = self.drive_folder(temp, "My Drive", "Project")
        (node / "docs" / "drive").symlink_to(target)
        return brain, target

    def assertNoMachinePath(self, temp, text):
        self.assertNotIn(str(temp), text)
        self.assertNotIn(os.path.realpath(temp), text)

    def test_url_is_proposed_with_a_missing_key_when_the_id_is_readable(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, target = self.linked(temp)

            result = self.run_validator(
                brain, fake_xattr_env(temp, {target: self.FOLDER_ID}))

            self.assertEqual(result.returncode, 0, result.stdout)
            warned = self.warnings(result)
            self.assertEqual(len(warned), 1, result.stdout)
            self.assertIn("declares no `artifacts:` key", warned[0])
            self.assertIn("`root: My Drive/Project`", warned[0])
            self.assertIn(f"`url: {FOLDERS}{self.FOLDER_ID}`", warned[0])
            self.assertIn("owner approval", warned[0])
            self.assertNoMachinePath(temp, result.stdout)

    def test_a_key_without_url_gets_a_note_not_a_warning(self):
        # `url` is optional and may be left out on purpose: no warning on every run.
        with tempfile.TemporaryDirectory() as temp:
            brain, target = self.linked(temp, KEY.format(root="My Drive/Project"))

            result = self.run_validator(
                brain, fake_xattr_env(temp, {target: self.FOLDER_ID}))

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.warnings(result), [], result.stdout)
            noted = [l for l in self.notes(result) if "url" in l]
            self.assertEqual(len(noted), 1, result.stdout)
            self.assertIn("has no `url` (optional)", noted[0])
            self.assertIn(f"`url: {FOLDERS}{self.FOLDER_ID}`", noted[0])
            self.assertIn("README edit: owner approval", noted[0])
            self.assertNotIn("PROBLEM", result.stdout)
            self.assertNoMachinePath(temp, result.stdout)

    def test_url_is_proposed_where_no_root_can_be(self):
        # Drive's "Other computers" has no My Drive or Shared drives anchor to name a root.
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp)
            target = self.drive_folder(temp, "Other computers", "Mac", "Project")
            (node / "docs" / "drive").symlink_to(target)

            result = self.run_validator(
                brain, fake_xattr_env(temp, {target: self.FOLDER_ID}))

            warned = "\n".join(self.warnings(result))
            self.assertIn("declares no `artifacts:` key", warned)
            self.assertIn(f"`url: {FOLDERS}{self.FOLDER_ID}`", warned)
            self.assertNotIn("root:", warned)
            self.assertNotIn("Other computers", warned)

    def test_id_is_read_from_the_resolved_target(self):
        # docs/drive -> alias/My Drive/Project, where alias is itself a symlink: the fake
        # answers only for the real path, as the real command need not follow links.
        with tempfile.TemporaryDirectory() as temp:
            brain, node = self.make_brain(temp, KEY.format(root="My Drive/Project"))
            target = self.drive_folder(temp, "My Drive", "Project")
            alias = Path(temp) / "alias"
            alias.symlink_to(target.parent.parent)
            (node / "docs" / "drive").symlink_to(alias / "My Drive" / "Project")

            result = self.run_validator(
                brain, fake_xattr_env(temp, {target: self.FOLDER_ID}))

            self.assertIn(f"`url: {FOLDERS}{self.FOLDER_ID}`",
                          "\n".join(self.notes(result)))

    def test_nothing_is_said_about_url_when_the_id_cannot_be_read(self):
        no_xattr, no_attribute = object(), object()
        cases = {
            "no xattr on PATH": no_xattr,
            "a folder without the attribute": no_attribute,
            "a value too short": "short",
            "a value not shaped like an id": "not an id!",
            "an id with other text": f"{self.FOLDER_ID} extra",
            "an empty value": "",
            "a failed read": {"stdout": self.FOLDER_ID + "\n", "exit": 1},
            # Reportedly what Drive for Desktop gives an item still uploading (XFE-231).
            "a temporary id": "local-" + self.FOLDER_ID,
        }
        for case, answer in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                brain, target = self.linked(temp)
                env = (no_xattr_env() if answer is no_xattr else
                       fake_xattr_env(temp, {} if answer is no_attribute
                                      else {target: answer}))

                missing = self.run_validator(brain, env)
                (brain / "spaces" / "project" / "README.md").write_text(
                    readme(KEY.format(root="My Drive/Project")), encoding="utf-8")
                declared = self.run_validator(brain, env)

                warned = "\n".join(self.warnings(missing))
                self.assertIn("declares no `artifacts:` key", warned)
                self.assertIn("`root: My Drive/Project`", warned)
                self.assertNotIn("url", warned)
                self.assertEqual(self.warnings(declared), [], declared.stdout)
                self.assertNotIn("url", "\n".join(self.notes(declared)))
                self.assertNotIn("local-", missing.stdout + declared.stdout)

    def test_a_hanging_xattr_is_no_answer(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, target = self.linked(temp, KEY.format(root="My Drive/Project"))
            hang = {"stdout": self.FOLDER_ID + "\n", "exit": 0, "sleep": 60}

            result = self.run_validator(brain, fake_xattr_env(temp, {target: hang}))

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.warnings(result), [], result.stdout)

    def test_declared_url_naming_another_folder_is_warned(self):
        with tempfile.TemporaryDirectory() as temp:
            brain, target = self.linked(temp, URL_KEY.format(
                root="My Drive/Project", url=f"{FOLDERS}{self.OTHER_ID}?usp=sharing"))

            result = self.run_validator(
                brain, fake_xattr_env(temp, {target: self.FOLDER_ID}))

            self.assertEqual(result.returncode, 0, result.stdout)
            warned = self.warnings(result)
            self.assertEqual(len(warned), 1, result.stdout)
            self.assertIn(self.OTHER_ID, warned[0])
            self.assertIn(self.FOLDER_ID, warned[0])
            self.assertIn("correct whichever is stale, with owner approval", warned[0])
            self.assertNoMachinePath(temp, result.stdout)

    def test_matching_copy_links_are_quiet(self):
        for url in (f"{FOLDERS}{self.FOLDER_ID}",
                    f"{FOLDERS}{self.FOLDER_ID}?usp=sharing",
                    f"https://drive.google.com/drive/u/1/folders/{self.FOLDER_ID}"
                    f"?usp=drive_link&resourcekey=0-AbC_123",
                    f"'{FOLDERS}{self.FOLDER_ID}?usp=sharing'   # Copy link"):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as temp:
                brain, target = self.linked(temp, URL_KEY.format(
                    root="My Drive/Project", url=url))

                readable = self.run_validator(
                    brain, fake_xattr_env(temp, {target: self.FOLDER_ID}))
                blind = self.run_validator(brain)

                self.assertEqual(self.warnings(readable), [], readable.stdout)
                self.assertEqual(self.warnings(blind), [], blind.stdout)

    def test_unusable_urls_are_warned_and_never_compared(self):
        cases = {
            f"{FOLDERS}<folder id>": "still a placeholder",
            f"https://drive.google.com/file/d/{self.OTHER_ID}/view": "not a Drive folder link",
            f"https://drive.google.com/open?id={self.OTHER_ID}": "not a Drive folder link",
            f"https://docs.google.com/drive/folders/{self.OTHER_ID}": "not a Drive folder link",
            f"http://drive.google.com/drive/folders/{self.OTHER_ID}": "not an https link",
            "drive.google.com/drive/folders/": "not an https link",
            FOLDERS: "carries no folder id",
            f"{FOLDERS}?usp=sharing": "carries no folder id",
            f"'{FOLDERS}{self.OTHER_ID}": "cannot be read",     # the closing quote forgotten
        }
        for url, expected in cases.items():
            with self.subTest(url=url), tempfile.TemporaryDirectory() as temp:
                brain, target = self.linked(temp, URL_KEY.format(
                    root="My Drive/Project", url=url))

                readable = self.run_validator(
                    brain, fake_xattr_env(temp, {target: self.FOLDER_ID}))
                blind = self.run_validator(brain)

                self.assertEqual(readable.returncode, 0, readable.stdout)
                warned = self.warnings(readable)
                self.assertEqual(len(warned), 1, readable.stdout)
                self.assertIn(expected, warned[0])
                self.assertIn(f"`url: {FOLDERS}{self.FOLDER_ID}`", warned[0])
                self.assertIn("owner approval", warned[0])
                self.assertNotIn("stale", warned[0])
                warned = self.warnings(blind)
                self.assertEqual(len(warned), 1, blind.stdout)
                self.assertIn(expected, warned[0])
                self.assertIn("Copy link", warned[0])
                self.assertNoMachinePath(temp, readable.stdout + blind.stdout)


class IndexLinkColumnTests(unittest.TestCase):
    DOC_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789-_"
    SHEET_ID = "1ZyXwVuTsRqPoNmLkJiHgFeDcBa98765"
    LEGACY_ID = "1LeGaCyBaCkUpAnDsYnC0123456789"
    FILE_ID = "1FiLeIdOnDiSkAbCdEfGhIjKlMnOp"
    NEW_FILE_ID = "1NeWeRuPlOaDzYxWvUtSrQpOnMl"

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

    def run_indexer(self, node, lang, env=None):
        brain = node.parents[1]
        result = subprocess.run(
            [sys.executable, str(INDEXER), "spaces/project", "--lang", lang],
            cwd=brain, capture_output=True, text=True, timeout=20,
            env=env or no_xattr_env(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "", result.stderr)
        return result, (node / "docs" / "index.md").read_text(encoding="utf-8")

    def file_url(self, file_id):
        return f"<https://drive.google.com/file/d/{file_id}/view>"

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
            self.assertIn("| `Tab.docx` | docx | 11 B | |\n", index)   # as before links
            self.assertNotIn("Drive folder", index)     # no folder id, no line
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


    def test_other_files_get_drive_urls_from_the_attribute(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            drive = Path(temp) / "drive"
            env = fake_xattr_env(temp, {drive / "songs" / "Tab.docx": self.FILE_ID,
                                        # pointers keep their stub's link, never this
                                        drive / "songs" / "Song.gdoc": self.NEW_FILE_ID})

            result, index = self.run_indexer(node, "en", env)

            self.assertEqual(self.row(index, "Tab.docx")[-1], self.file_url(self.FILE_ID))
            self.assertEqual(self.row(index, "songs/Song.gdoc")[-1],
                             f"<https://drive.google.com/open?id={self.DOC_ID}>")
            self.assertIn("5 Drive link(s)", result.stdout)
            self.assertNotIn("previous index", result.stdout)

    def test_unreadable_id_keeps_the_previous_link_with_a_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            drive = Path(temp) / "drive"
            self.run_indexer(node, "en", fake_xattr_env(
                temp, {drive / "songs" / "Tab.docx": self.FILE_ID}))

            result, index = self.run_indexer(node, "en")    # a machine with no xattr

            self.assertEqual(self.row(index, "Tab.docx")[-1], self.file_url(self.FILE_ID))
            warning = [l for l in result.stdout.splitlines() if "WARNING" in l]
            self.assertEqual(len(warning), 1, result.stdout)
            self.assertIn("1 link(s) kept from the previous index", warning[0])
            self.assertIn("songs/Tab.docx", warning[0])
            self.assertIn("5 Drive link(s)", result.stdout)

    def test_an_answer_that_is_no_id_keeps_the_previous_link(self):
        cases = {
            "a value too short": "short",
            "a value not shaped like an id": "not an id!",
            "an id with other text": f"{self.NEW_FILE_ID} extra",
            "an empty value": "",
            "a failed read": {"stdout": self.NEW_FILE_ID + "\n", "exit": 1},
        }
        for case, answer in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                node = self.build(temp)
                tab = Path(temp) / "drive" / "songs" / "Tab.docx"
                self.run_indexer(node, "en", fake_xattr_env(temp, {tab: self.FILE_ID}))

                result, index = self.run_indexer(
                    node, "en", fake_xattr_env(temp, {tab: answer}))

                self.assertEqual(self.row(index, "Tab.docx")[-1],
                                 self.file_url(self.FILE_ID))
                self.assertNotIn(self.NEW_FILE_ID, index)
                warning = [l for l in result.stdout.splitlines() if "WARNING" in l]
                self.assertEqual(len(warning), 1, result.stdout)
                self.assertIn("1 link(s) kept from the previous index", warning[0])
                self.assertIn("songs/Tab.docx", warning[0])

    def test_a_temporary_id_is_never_written_and_is_said_apart(self):
        for temporary in ("local-1234567890", "local-1"):
            with self.subTest(temporary=temporary), tempfile.TemporaryDirectory() as temp:
                node = self.build(temp)
                tab = Path(temp) / "drive" / "songs" / "Tab.docx"
                no_id, _ = self.run_indexer(node, "en")
                (node / "docs" / "index.md").unlink()

                result, index = self.run_indexer(
                    node, "en", fake_xattr_env(temp, {tab: temporary}))

                self.assertEqual(self.row(index, "Tab.docx")[-1], "")
                self.assertNotIn("local-", index)
                unread = re.search(r"(\d+) file\(s\) had no readable", no_id.stdout)
                self.assertIn(f"{int(unread.group(1)) - 1} file(s) had no readable",
                              result.stdout)
                uploading = [l for l in result.stdout.splitlines() if "uploading" in l]
                self.assertEqual(len(uploading), 1, result.stdout)
                self.assertIn("1 item(s) still uploading", uploading[0])
                self.assertIn("songs/Tab.docx", uploading[0])
                self.assertIn("Regenerate the index once Drive shows them synced",
                              uploading[0])
                self.assertNotIn("WARNING", result.stdout)

    def test_a_temporary_id_keeps_the_previous_link(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            tab = Path(temp) / "drive" / "songs" / "Tab.docx"
            self.run_indexer(node, "en", fake_xattr_env(temp, {tab: self.FILE_ID}))

            result, index = self.run_indexer(
                node, "en", fake_xattr_env(temp, {tab: "local-" + self.NEW_FILE_ID}))

            self.assertEqual(self.row(index, "Tab.docx")[-1], self.file_url(self.FILE_ID))
            self.assertNotIn(self.NEW_FILE_ID, index)
            self.assertIn("1 link(s) kept from the previous index", result.stdout)
            self.assertIn("1 item(s) still uploading", result.stdout)

    def test_the_kept_links_warning_names_five_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            songs = Path(temp) / "drive" / "songs"
            answers = {songs / "Tab.docx": self.FILE_ID}
            for i in range(6):
                (songs / f"Take{i}.pdf").write_bytes(b"%PDF-1.4")
                answers[songs / f"Take{i}.pdf"] = f"1TaKeFiLe{i}AbCdEfGhIjK"
            self.run_indexer(node, "en", fake_xattr_env(temp, answers))

            result, index = self.run_indexer(node, "en")

            for path, file_id in answers.items():
                self.assertEqual(self.row(index, path.name)[-1], self.file_url(file_id))
            warning = [l for l in result.stdout.splitlines() if "WARNING" in l]
            self.assertEqual(len(warning), 1, result.stdout)
            self.assertIn("7 link(s) kept from the previous index", warning[0])
            self.assertEqual(warning[0].count("songs/"), 5, warning[0])
            self.assertTrue(warning[0].endswith(", and 2 more"), warning[0])

    def test_a_readable_id_replaces_the_previous_link(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            tab = Path(temp) / "drive" / "songs" / "Tab.docx"
            self.run_indexer(node, "en", fake_xattr_env(temp, {tab: self.FILE_ID}))

            result, index = self.run_indexer(
                node, "en", fake_xattr_env(temp, {tab: self.NEW_FILE_ID}))

            self.assertEqual(self.row(index, "Tab.docx")[-1],
                             self.file_url(self.NEW_FILE_ID))
            self.assertNotIn(self.FILE_ID, index)
            self.assertNotIn("WARNING", result.stdout)

    def test_a_link_is_never_carried_to_another_path(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            ids = ["1RoOtLeVeLtAbAbCdEfGhIjK", "1OtHeRfOlDeRtAbAbCdEfGh",
                   "1RoOtSoNgPoInTeRaBcDeFgH", "1OlDdOcXnOtHeReAbCdEfGh",
                   "1TwIcEnAmEdOnEaBcDeFgHiJ", "1TwIcEnAmEdTwOaBcDeFgHiJ"]
            (Path(temp) / "drive" / "songs" / "Zed.pdf").write_bytes(b"%PDF-1.4")
            (node / "docs" / "index.md").write_text("\n".join([
                "## Root", "",
                "| File | Type | Size | Link |", "|---|---|---|---|",
                f"| `Tab.docx` | docx | 15 B | {self.file_url(ids[0])} |", "",
                "## `other/`", "",
                "| File | Type | Size | Link |", "|---|---|---|---|",
                f"| `Tab.docx` | docx | 15 B | {self.file_url(ids[1])} |", "",
                "## `songs/`", "",
                "| File | Type | Size | Link |", "|---|---|---|---|",
                f"| `Old.docx` | docx | 1 KB | {self.file_url(ids[3])} |",
                "| `Tab.docx` | docx | 15 B | <https://example.com/Tab.docx> |",
                # Two rows naming one path: neither link can be told to be the right one.
                f"| `Zed.pdf` | pdf | 8 B | {self.file_url(ids[4])} |",
                f"| `Zed.pdf` | pdf | 8 B | {self.file_url(ids[5])} |", "",
                "## Accepted pointers (1)", "",
                "| File | Kind | Link |", "|---|---|---|",
                f"| `Deck.gslides/x` | Google Slides | {self.file_url(ids[2])} |",
                f"| `Song.gdoc` | Google Doc | {self.file_url(ids[2])} |", "",
            ]), encoding="utf-8")

            result, index = self.run_indexer(node, "en")

            self.assertEqual(self.row(index, "Tab.docx")[-1], "")
            self.assertEqual(self.row(index, "Deck.gslides")[-1], "")
            self.assertEqual(self.row(index, "Zed.pdf")[-1], "")
            for file_id in ids:
                self.assertNotIn(file_id, index)
            self.assertNotIn("example.com", index)
            self.assertNotIn("WARNING", result.stdout)

    def test_an_unreadable_pointer_stub_keeps_its_previous_link(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            self.run_indexer(node, "en")
            # Still streaming, say: the stub no longer reads, the file is the same one.
            (Path(temp) / "drive" / "Inventory.gsheet").write_text("", encoding="utf-8")

            result, index = self.run_indexer(node, "en")

            self.assertEqual(
                self.row(index, "Inventory.gsheet")[-1],
                f"<https://drive.google.com/open?id={self.SHEET_ID}&resourcekey=0-AbC_123>")
            self.assertIn("Inventory.gsheet", "\n".join(
                l for l in result.stdout.splitlines() if "WARNING" in l))

    def test_previous_index_is_read_in_either_language(self):
        for before, after in (("es", "en"), ("en", "es")):
            with self.subTest(before=before), tempfile.TemporaryDirectory() as temp:
                node = self.build(temp)
                drive = Path(temp) / "drive"
                (drive / "Setlist.pdf").write_bytes(b"%PDF-1.4")
                self.run_indexer(node, before, fake_xattr_env(temp, {
                    drive / "songs" / "Tab.docx": self.FILE_ID,
                    drive / "Setlist.pdf": self.NEW_FILE_ID}))
                for stub in ("songs/Song.gdoc", "Inventory.gsheet"):   # accepted, pending
                    (drive / stub).write_text("", encoding="utf-8")

                result, index = self.run_indexer(node, after)

                self.assertEqual(self.row(index, "Tab.docx")[-1], self.file_url(self.FILE_ID))
                self.assertEqual(self.row(index, "Setlist.pdf")[-1],
                                 self.file_url(self.NEW_FILE_ID))
                self.assertIn(f"open?id={self.DOC_ID}", self.row(index, "songs/Song.gdoc")[-1])
                self.assertIn(f"open?id={self.SHEET_ID}", self.row(index, "Inventory.gsheet")[-1])
                self.assertIn("4 link(s) kept from the previous index", result.stdout)

    def test_a_previous_link_is_matched_across_unicode_forms(self):
        # macOS may hand back a decomposed name; the previous index may hold either form.
        composed = unicodedata.normalize("NFC", "Canción.docx")
        decomposed = unicodedata.normalize("NFD", "Canción.docx")
        for on_disk, listed in ((decomposed, composed), (composed, decomposed)):
            with self.subTest(on_disk=ascii(on_disk)), tempfile.TemporaryDirectory() as temp:
                node = self.build(temp)
                (Path(temp) / "drive" / on_disk).write_bytes(b"ab")
                (node / "docs" / "index.md").write_text("\n".join([
                    "## Root", "",
                    "| File | Type | Size | Link |", "|---|---|---|---|",
                    f"| `{listed}` | docx | 2 B | {self.file_url(self.FILE_ID)} |", "",
                ]), encoding="utf-8")

                result, index = self.run_indexer(node, "en")

                self.assertEqual(self.row(index, on_disk)[-1], self.file_url(self.FILE_ID))
                warning = [l for l in result.stdout.splitlines() if "WARNING" in l]
                self.assertEqual(len(warning), 1, result.stdout)
                self.assertIn("1 link(s) kept from the previous index", warning[0])

    def test_awkward_names_keep_their_own_links(self):
        # A folder named like either language's root keeps its own heading, so its files
        # are never read back as root files; a | in an extension does not hide a row.
        for lang in ("en", "es"):
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as temp:
                node = self.build(temp)
                drive = Path(temp) / "drive"
                answers = {}
                for i, path in enumerate((drive / "Tab.docx", drive / "(root)" / "Tab.docx",
                                          drive / "(raíz)" / "Tab.docx", drive / "x.p|f")):
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(b"ab")
                    answers[path] = f"1AwKwArDnAmE{i}AbCdEfGhIj"
                _, first = self.run_indexer(node, lang, fake_xattr_env(temp, answers))

                result, second = self.run_indexer(node, lang)

                self.assertIn("## `(root)/`", first)
                self.assertIn("## `(raíz)/`", first)
                for file_id in answers.values():
                    self.assertEqual(first.count(file_id), 1, first)
                self.assertEqual(second.split("\n## ")[1:], first.split("\n## ")[1:])
                self.assertIn("4 link(s) kept from the previous index", result.stdout)

    def test_after_one_timeout_no_other_file_is_asked(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            songs = Path(temp) / "drive" / "songs"
            (songs / "Zed.pdf").write_bytes(b"%PDF-1.4")
            env = fake_xattr_env(temp, {
                songs / "Tab.docx": {"stdout": self.FILE_ID + "\n", "exit": 0, "sleep": 60},
                songs / "Zed.pdf": self.NEW_FILE_ID})

            result, index = self.run_indexer(node, "en", env)

            self.assertEqual(self.row(index, "Tab.docx")[-1], "")
            self.assertEqual(self.row(index, "Zed.pdf")[-1], "")
            asked = Path(env["FAKE_XATTR_ANSWERS"] + ".log").read_text(encoding="utf-8")
            self.assertTrue(asked.endswith(os.path.realpath(songs / "Tab.docx") + "\n"),
                            asked)
            self.assertNotIn("Zed.pdf", asked)
            self.assertIn("had no readable Drive id", result.stdout)

    def test_links_dropped_by_a_folder_now_summarised_are_counted(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            takes = Path(temp) / "drive" / "takes"
            takes.mkdir()
            answers = {}
            for i in range(COLLAPSE_OVER + 1):
                answers[takes / f"take{i:03}.pdf"] = f"1TaKeIdNuMbEr{i:03}AbCdEfGh"
            last = takes / f"take{COLLAPSE_OVER:03}.pdf"
            for path in answers:
                if path != last:
                    path.write_bytes(b"%PDF-1.4")
            env = fake_xattr_env(temp, answers)
            listed, first = self.run_indexer(node, "en", env)
            last.write_bytes(b"%PDF-1.4")

            grown, second = self.run_indexer(node, "en", env)
            again, third = self.run_indexer(node, "en", env)

            self.assertEqual(first.count("1TaKeIdNuMbEr"), COLLAPSE_OVER, first)
            self.assertNotIn("dropped", listed.stdout)
            self.assertNotIn("1TaKeIdNuMbEr", second)
            dropped = [l for l in grown.stdout.splitlines() if "dropped" in l]
            self.assertEqual(len(dropped), 1, grown.stdout)
            self.assertIn(f"{COLLAPSE_OVER} link(s) from the previous index dropped: takes/",
                          dropped[0])
            self.assertIn(f"more than {COLLAPSE_OVER} files", dropped[0])
            # No folder id was readable, so no folder line to point to.
            self.assertNotIn("Drive folder:", second)
            self.assertIn("cite those files through each file's own Copy link", dropped[0])
            self.assertNotIn("dropped", again.stdout)
            self.assertEqual(third, second)

    def test_the_dropped_links_line_points_to_a_folder_line_only_where_one_is_written(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            takes = Path(temp) / "drive" / "takes"
            takes.mkdir()
            answers = {takes: "1TaKeSfOlDeRiDaBcDeFgHiJk"}
            for i in range(COLLAPSE_OVER):
                (takes / f"take{i:03}.pdf").write_bytes(b"%PDF-1.4")
                answers[takes / f"take{i:03}.pdf"] = f"1TaKeIdNuMbEr{i:03}AbCdEfGh"
            env = fake_xattr_env(temp, answers)
            self.run_indexer(node, "en", env)
            (takes / "extra.pdf").write_bytes(b"%PDF-1.4")

            grown, index = self.run_indexer(node, "en", env)

            self.assertEqual(self.folder_line(index, "## `takes/`"),
                             f"<{FOLDERS}1TaKeSfOlDeRiDaBcDeFgHiJk>")
            self.assertIn("cite those files through the Drive folder link under its heading, "
                          "or each file's own Copy link", grown.stdout)

    def folder_line(self, index, heading, lang="en"):
        """The folder link line in a heading's section, or None."""
        section = index.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]
        label = {"en": "Drive folder: ", "es": "Carpeta en Drive: "}[lang]
        lines = [l for l in section.splitlines() if l.startswith(label)]
        assert len(lines) <= 1, section
        return lines[0][len(label):] if lines else None

    def folders(self, temp):
        """The stand-in Drive with a root file and a summarised folder, and their ids."""
        drive = Path(temp) / "drive"
        (drive / "Setlist.pdf").write_bytes(b"%PDF-1.4")
        (drive / "assets").mkdir()
        for i in range(COLLAPSE_OVER + 1):
            (drive / "assets" / f"img{i:03}.png").write_bytes(b"\x89PNG")
        return {drive: self.ROOT_FOLDER_ID, drive / "songs": self.SONGS_FOLDER_ID,
                drive / "assets": self.ASSETS_FOLDER_ID}

    ROOT_FOLDER_ID = "1RoOtFoLdErIdAbCdEfGhIjKlM"
    SONGS_FOLDER_ID = "1SoNgSfOlDeRiDaBcDeFgHiJkL"
    ASSETS_FOLDER_ID = "1AsSeTsFoLdErIdAbCdEfGhIjK"

    def test_every_folder_heading_carries_its_own_drive_link(self):
        for lang, root_head in (("en", "## Root"), ("es", "## Raíz")):
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as temp:
                node = self.build(temp)
                ids = self.folders(temp)

                result, index = self.run_indexer(node, lang, fake_xattr_env(temp, ids))

                self.assertEqual(self.folder_line(index, root_head, lang),
                                 f"<{FOLDERS}{self.ROOT_FOLDER_ID}>")
                self.assertEqual(self.folder_line(index, "## `songs/`", lang),
                                 f"<{FOLDERS}{self.SONGS_FOLDER_ID}>")
                # Summarised by type, and still linked as a whole.
                self.assertEqual(self.folder_line(index, "## `assets/`", lang),
                                 f"<{FOLDERS}{self.ASSETS_FOLDER_ID}>")
                self.assertNotIn("img000.png", index)
                self.assertNotIn("previous index", result.stdout)
                self.assertIn("7 Drive link(s)", result.stdout)    # 4 pointers, 3 folders

    def test_a_folder_link_is_kept_when_unreadable_and_never_moved(self):
        for before, after in (("en", "es"), ("es", "en")):
            with self.subTest(before=before), tempfile.TemporaryDirectory() as temp:
                node = self.build(temp)
                ids = self.folders(temp)
                drive = Path(temp) / "drive"
                self.run_indexer(node, before, fake_xattr_env(temp, ids))
                (drive / "assets").rename(drive / "pictures")

                result, index = self.run_indexer(node, after)    # no xattr

                root_head = {"en": "## Root", "es": "## Raíz"}[after]
                self.assertEqual(self.folder_line(index, root_head, after),
                                 f"<{FOLDERS}{self.ROOT_FOLDER_ID}>")
                self.assertEqual(self.folder_line(index, "## `songs/`", after),
                                 f"<{FOLDERS}{self.SONGS_FOLDER_ID}>")
                self.assertIsNone(self.folder_line(index, "## `pictures/`", after))
                self.assertNotIn(self.ASSETS_FOLDER_ID, index)
                warning = [l for l in result.stdout.splitlines() if "WARNING" in l]
                self.assertEqual(len(warning), 1, result.stdout)
                self.assertIn("2 link(s) kept from the previous index", warning[0])
                self.assertIn("the root folder", warning[0])
                self.assertIn("songs/", warning[0])
                # Folders without a link (pictures/) are not counted with the files that
                # lack one: the stubs that do not read (Deck, Odd, Array, Deep, Pipe), and
                # Setlist.pdf and Tab.docx, whose ids nobody read, are all there is.
                unread = 7 if hasattr(os, "mkfifo") else 6
                self.assertIn(f"\n  {unread} file(s) had no readable Drive id", result.stdout)

    def test_a_folder_still_uploading_gets_no_line(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            songs = Path(temp) / "drive" / "songs"

            result, index = self.run_indexer(node, "en", fake_xattr_env(
                temp, {songs: "local-" + self.SONGS_FOLDER_ID}))

            self.assertIsNone(self.folder_line(index, "## `songs/`"))
            self.assertNotIn("local-", index)
            self.assertIn("1 item(s) still uploading", result.stdout)
            self.assertIn(": songs/.", result.stdout)

    def test_a_temporary_id_in_a_stub_or_the_previous_index_is_never_written(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            drive = Path(temp) / "drive"
            (drive / "New.gdoc").write_text(json.dumps({"doc_id": "local-1234567890abc"}),
                                            encoding="utf-8")
            (drive / "Setlist.pdf").write_bytes(b"%PDF-1.4")
            (node / "docs" / "index.md").write_text("\n".join([
                "## Root", "",
                f"Drive folder: <{FOLDERS}local-RoOtFoLdEr1>", "",
                "| File | Type | Size | Link |", "|---|---|---|---|",
                "| `Setlist.pdf` | pdf | 8 B | <https://drive.google.com/file/d/local-12345/view> |",
                "",
                "## `songs/`", "",
                "| File | Type | Size | Link |", "|---|---|---|---|",
                f"| `Tab.docx` | docx | 11 B | {self.file_url(self.FILE_ID)} |", "",
                "## Google pointers to deal with", "",
                "| File | Kind | Link |", "|---|---|---|",
                "| `Deck.gslides` | Google Slides | <https://drive.google.com/open?id=local-99999> |",
                "",
            ]), encoding="utf-8")

            result, index = self.run_indexer(node, "en", fake_xattr_env(
                temp, {drive: "local-RoOtFoLdEr1", drive / "Setlist.pdf": "local-12345"}))

            self.assertNotIn("local-", index)
            self.assertEqual(self.row(index, "New.gdoc")[-1], "")
            self.assertEqual(self.row(index, "Setlist.pdf")[-1], "")
            self.assertEqual(self.row(index, "Deck.gslides")[-1], "")
            self.assertIsNone(self.folder_line(index, "## Root"))
            # A real link beside them is still kept.
            self.assertEqual(self.row(index, "Tab.docx")[-1], self.file_url(self.FILE_ID))
            self.assertIn("2 item(s) still uploading", result.stdout)
            self.assertIn(": the root folder, Setlist.pdf.", result.stdout)
            self.assertIn("1 link(s) kept from the previous index", result.stdout)

    def test_folder_lines_follow_the_same_reading_rules_as_rows(self):
        composed = unicodedata.normalize("NFC", "Canción")
        decomposed = unicodedata.normalize("NFD", "Canción")
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            drive = Path(temp) / "drive"
            (drive / composed).mkdir()
            (drive / composed / "a.pdf").write_bytes(b"%PDF-1.4")
            (node / "docs" / "index.md").write_text("\n".join([
                # Listed decomposed, as macOS may have written it: still the same folder.
                f"## `{decomposed}/`", "",
                f"Drive folder: <{FOLDERS}{self.ROOT_FOLDER_ID}>", "",
                # Two lines naming one folder: neither can be told to be the right one.
                "## `songs/`", "",
                f"Drive folder: <{FOLDERS}{self.SONGS_FOLDER_ID}>",
                f"Carpeta en Drive: <{FOLDERS}{self.ASSETS_FOLDER_ID}>", "",
                # A file's link is never a folder's: `songs` the file is not `songs/`.
                "## Root", "",
                "| File | Type | Size | Link |", "|---|---|---|---|",
                f"| `songs` | — | 1 B | {self.file_url(self.FILE_ID)} |", "",
            ]), encoding="utf-8")

            result, index = self.run_indexer(node, "en")

            self.assertEqual(self.folder_line(index, f"## `{composed}/`"),
                             f"<{FOLDERS}{self.ROOT_FOLDER_ID}>")
            self.assertIsNone(self.folder_line(index, "## `songs/`"))
            self.assertNotIn(self.SONGS_FOLDER_ID, index)
            self.assertNotIn(self.FILE_ID, index)
            self.assertIn("1 link(s) kept from the previous index", result.stdout)

    def test_a_line_separator_in_a_folder_name_moves_no_link(self):
        # The index is written one line per "\n"; a name may hold U+2028, which other
        # line splitting would read as a new heading for another folder.
        odd = "x\u2028## `b"
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            drive = Path(temp) / "drive"
            for name in (odd, "b"):
                (drive / name).mkdir()
                (drive / name / "Tab.docx").write_bytes(b"ab")
            self.run_indexer(node, "en", fake_xattr_env(temp, {
                drive / odd: self.ROOT_FOLDER_ID, drive / odd / "Tab.docx": self.FILE_ID}))

            _, index = self.run_indexer(node, "en")

            self.assertIsNone(self.folder_line(index, "## `b/`"))
            b = index.split("\n## `b/`\n", 1)[1].split("\n## ", 1)[0]
            self.assertNotIn(self.FILE_ID, b)
            self.assertEqual(index.count(self.ROOT_FOLDER_ID), 1)
            self.assertEqual(index.count(self.FILE_ID), 1)

    def test_collapsed_folders_ask_for_no_ids_and_have_no_cells(self):
        with tempfile.TemporaryDirectory() as temp:
            node = self.build(temp)
            assets = Path(temp) / "drive" / "assets"
            assets.mkdir()
            answers = {}
            for i in range(COLLAPSE_OVER + 1):
                (assets / f"img{i:03}.png").write_bytes(b"\x89PNG")
                answers[assets / f"img{i:03}.png"] = f"1AsSeTiMaGe{i:03}AbCdEfGhIj"

            env = fake_xattr_env(temp, answers)

            _, index = self.run_indexer(node, "en", env)

            self.assertIn("## `assets/`", index)
            self.assertNotIn("1AsSeTiMaGe", index)
            self.assertNotIn("img000.png", index)
            asked = Path(env["FAKE_XATTR_ANSWERS"] + ".log").read_text(encoding="utf-8")
            self.assertIn("Tab.docx", asked)
            self.assertNotIn("img000.png", asked)


if __name__ == "__main__":
    unittest.main()
