#!/usr/bin/env python3
"""Regenerate a node's docs/index.md from the artifacts in its cloud folder.

    python3 <this script> spaces/guitar
    python3 <this script> spaces/guitar /path/to/drive/root
    python3 <this script> spaces/guitar --lang en

Run it from the brain's root. The regeneration line written into each index names the
owning skill without persisting this machine's installed-skill or plugin-cache path.

The index is the bridge across the git/cloud boundary. Running this command is an
explicit request to create or replace the durable `docs/index.md`; do not run it in an
unattended pass. The files themselves are
gitignored, so this generated list is what travels with the repo and is all cloud
chat can see. Regenerate it; never hand-edit.

LANGUAGE: the index follows the NODE's language, detected from its own README and
files, because SKILL.md says not to impose the framework's language on someone's
material -- and this script used to do exactly that, emitting Spanish everywhere.
The detected language is printed; override it with --lang es|en when it guesses wrong.

LINKS: every per-file table carries a Link column, because the Reader and agents on the MCP
server cannot open docs/ -- only Drive can -- so a note that cites an artifact someone
will open carries its Drive URL, and this index is where to copy it from. Google pointer
files (.gdoc, .gsheet, .gslides) hold their Drive file id on disk, so their link is
exact. Any other file's id comes, with no Drive API call, from the extended attribute
Drive for Desktop keeps on it on macOS (com.google.drivefs.item-id#S), and its link is
https://drive.google.com/file/d/<id>/view. Where no id can be read -- another OS, Drive
not running, a pointer stub still streaming -- the cell keeps the link the previous
docs/index.md had for that same path, with a warning, so regenerating on a machine that
cannot read ids never blanks links another machine wrote. Failing that it stays EMPTY. A
link is never guessed and never carried to another path: a search by name can land on
the wrong copy, and a wrong link is worse than none. Folders collapsed into a type
summary list no files, so they have no cells to fill.
"""
import os, sys, datetime, json, pathlib, re, shutil, subprocess, unicodedata

COLLAPSE_OVER = 12   # folders bigger than this are summarised by type
POINTERS = {".gdoc": "Google Doc", ".gsheet": "Google Sheet", ".gslides": "Google Slides"}
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,}")
# Where Drive for Desktop on macOS keeps a synced file's Drive id.
ITEM_ID_XATTR = "com.google.drivefs.item-id#S"
XATTR_TIMEOUT = 5    # seconds; after one timeout no other file is asked
# A row of an index this script wrote, with a Drive link: `name`, the cells between, link.
OLD_ROW = re.compile(r"\| `(.+)` \|(.*)\| *<(https://drive\.google\.com/[^\s<>|]+)> *\|")

ES_HINTS = (" que ", " de la ", " para ", " con ", " los ", " las ", " una ", " esta ",
            " como ", " pero ", " porque ", " cuando ", " donde ", " del ", " se ")
EN_HINTS = (" the ", " and ", " of the ", " with ", " this ", " for ", " from ",
            " which ", " when ", " where ", " about ", " that ", " is ")

STRINGS = {
    "es": {
        "title":      "# Índice de artefactos — `{node}/docs/drive`",
        "generated":  "**Generado — no editar a mano.** Para actualizarlo, cargar "
                      "`itakua-map` y regenerar el índice de artefactos de `{node}`.",
        "summary":    "{count} archivos · {size} de contenido real · actualizado {date}",
        "root_key":   "(raíz)",
        "root_head":  "## Raíz",
        "folder_sub": "*{n} archivos · {size}*",
        "collapsed":  "*Carpeta de assets — resumida por tipo.*",
        "th_type":    "| Tipo | Archivos | Tamaño |",
        "th_file":    "| Archivo | Tipo | Tamaño | Enlace |",
        "ptr_head":   "## ⚠️ Punteros de Google pendientes",
        "ptr_body":   ["Cada uno pesa 176 bytes y **no se puede leer ni editar en disco** — son enlaces.",
                       "Migrar a markdown en git, o exportar a un formato real.",
                       "Si alguno debe quedarse así, agregarlo a `docs/pointers-ok.md`."],
        "ptr_th":     "| Archivo | Tipo | Enlace |",
        "ptr_ok":     "## Punteros aceptados ({n})",
        "ptr_ok_sub": "Se quedan como Google Docs a propósito — ver `docs/pointers-ok.md`.",
        "orph_head":  "## 🚨 Archivos huérfanos — en NINGÚN sistema",
        "orph_lead":  "**{n} archivos ({size})** están dentro de `docs/` pero fuera de `docs/drive/`.",
        "orph_bul":   ["- `**/docs/*` los ignora → **no están en git**",
                       "- No cuelgan del symlink → **no están en Drive**"],
        "orph_tail":  "No tienen respaldo en ningún lado. Moverlos a `docs/drive/` o pedir aprobación al dueño antes de borrarlos.",
        "orph_th":    "| Archivo |",
        "orph_more":  "| *… y {n} más* |",
    },
    "en": {
        "title":      "# Artifact index — `{node}/docs/drive`",
        "generated":  "**Generated — do not hand-edit.** To refresh it, load "
                      "`itakua-map` and regenerate the artifact index for `{node}`.",
        "summary":    "{count} files · {size} of real content · updated {date}",
        "root_key":   "(root)",
        "root_head":  "## Root",
        "folder_sub": "*{n} files · {size}*",
        "collapsed":  "*Asset folder — summarised by type.*",
        "th_type":    "| Type | Files | Size |",
        "th_file":    "| File | Type | Size | Link |",
        "ptr_head":   "## ⚠️ Google pointers to deal with",
        "ptr_body":   ["Each is 176 bytes and **cannot be read or edited on disk** — they are links.",
                       "Migrate to markdown in git, or export to a real format.",
                       "If one should stay as it is, add it to `docs/pointers-ok.md`."],
        "ptr_th":     "| File | Kind | Link |",
        "ptr_ok":     "## Accepted pointers ({n})",
        "ptr_ok_sub": "Deliberately left as Google files — see `docs/pointers-ok.md`.",
        "orph_head":  "## 🚨 Orphan files — in NO system at all",
        "orph_lead":  "**{n} files ({size})** are inside `docs/` but outside `docs/drive/`.",
        "orph_bul":   ["- `**/docs/*` ignores them → **not in git**",
                       "- They do not hang off the symlink → **not in cloud storage**"],
        "orph_tail":  "They are backed up nowhere. Move them under `docs/drive/`, or obtain owner approval before deleting them.",
        "orph_th":    "| File |",
        "orph_more":  "| *… and {n} more* |",
    },
}


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def pointer_link(path):
    """The Drive URL of a Google pointer file, from the id it holds, or "".

    Drive for Desktop writes a small JSON stub -- {"doc_id": ..., "resource_key": ...,
    "email": ...}; older Backup and Sync stubs carry doc_id too. Anything unreadable,
    still streaming, or not shaped like a Drive id gives "", never a guess. The email
    is never copied into the index.
    """
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as f:
            data = json.loads(f.read(65536).decode("utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return ""
    if not isinstance(data, dict):
        return ""
    file_id = data.get("doc_id")
    if not isinstance(file_id, str):
        rid = data.get("resource_id")
        m = re.fullmatch(r"(?:document|spreadsheet|presentation):(.+)", rid) \
            if isinstance(rid, str) else None
        file_id = m.group(1) if m else ""
    if not DRIVE_ID.fullmatch(file_id):
        return ""
    url = f"https://drive.google.com/open?id={file_id}"
    key = data.get("resource_key")
    if isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_-]+", key):
        url += f"&resourcekey={key}"
    return url


xattr_cmd = shutil.which("xattr")    # Apple's; without one, no file's id is read


def drive_item_id(path):
    """The Drive id Drive for Desktop keeps on a synced file, or "".

    Read with xattr on the resolved path, so nothing depends on xattr following a
    symlink. No command, no attribute, an error or an answer not shaped like a Drive id
    all give "", never a guess. A timeout means Drive is not answering: the files after
    it are not asked, and keep their previous links instead.
    """
    global xattr_cmd
    if not xattr_cmd:
        return ""
    try:
        result = subprocess.run((xattr_cmd, "-p", ITEM_ID_XATTR, os.path.realpath(path)),
                                stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=XATTR_TIMEOUT)
    except subprocess.TimeoutExpired:
        xattr_cmd = None
        return ""
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    value = result.stdout.decode("utf-8", "replace").strip()
    return value if result.returncode == 0 and DRIVE_ID.fullmatch(value) else ""


def file_link(path):
    """The Drive URL of a file that is not a Google pointer, from its Drive id, or ""."""
    file_id = drive_item_id(path)
    return f"https://drive.google.com/file/d/{file_id}/view" if file_id else ""


def previous_links(index):
    """The Drive link each path had in the index about to be replaced, by NFC path.

    Read back from the tables this script writes, in either language: under the root
    heading or a folder's (## `<folder>/`) a row names a file in that folder; under any
    other heading (the pointer tables) it names its whole path. Only drive.google.com
    links are kept, each for the path its own row names and no other; a path two rows
    give different links is ambiguous, and neither is kept.
    """
    try:
        text = pathlib.Path(index).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}
    roots = {S["root_head"] for S in STRINGS.values()}
    links, ambiguous, folder = {}, set(), None
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("## "):
            m = re.fullmatch(r"## `(.+)/`", line)
            folder = m.group(1) if m else "" if line in roots else None
            continue
        m = OLD_ROW.fullmatch(line)
        if not m:
            continue
        name, between, url = m.groups()
        # File | Kind | Link in the pointer tables; File | Type | Size | Link under a
        # folder, where Type is the file's extension and may hold a | of its own.
        if folder is None and "|" not in between:
            path = name
        elif folder is not None and "|" in between:
            path = f"{folder}/{name}" if folder else name
        else:
            continue
        path = nfc(path)
        if links.setdefault(path, url) != url:
            ambiguous.add(path)
    return {path: url for path, url in links.items() if path not in ambiguous}


def nfc(text):
    # macOS may hand back decomposed names; the previous index may hold either form.
    return unicodedata.normalize("NFC", text)


def link_cell(url):
    return f"<{url}>" if url else ""


def domain_of(node):
    """Top-level NODE name, not the first path component.

    `domain:` groups files across the repo, so it must be the node a reader would
    name -- 'guitar', not the container folder 'spaces' that every node shares.
    """
    parts = [p for p in node.split("/") if p and p != "."]
    if parts and parts[0] == "spaces":
        parts = parts[1:]
    return parts[0] if parts else node


def detect_language(node):
    """Read the node's own material and match it. Defaults to English on a tie.

    A first node with nothing in it yet will tie and get English; that is the same
    answer SKILL.md gives for a brain with nothing to read, and the index is
    regenerated anyway once the node has content.
    """
    texts, p = [], pathlib.Path(node)
    readme = p / "README.md"
    if readme.is_file():
        texts.append(readme.read_text(encoding="utf-8", errors="ignore"))
    for slot in ("notes", "log"):
        d = p / slot
        if d.is_dir():
            for f in sorted(d.rglob("*.md"))[:6]:
                texts.append(f.read_text(encoding="utf-8", errors="ignore"))
    blob = " " + " ".join(texts).lower().replace("\n", " ") + " "
    es = sum(blob.count(w) for w in ES_HINTS)
    en = sum(blob.count(w) for w in EN_HINTS)
    return "es" if es > en else "en"


def main():
    args = [a for a in sys.argv[1:]]
    lang = None
    if "--lang" in args:
        i = args.index("--lang")
        if i + 1 >= len(args) or args[i + 1] not in STRINGS:
            sys.exit("usage: --lang es|en")
        lang = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit("usage: index-artifacts.py <node> [drive-root] [--lang es|en]")

    node = args[0].rstrip("/")
    root = args[1] if len(args) > 1 else os.path.join(node, "docs", "drive")
    if not os.path.isdir(root):
        sys.exit(f"error: {root} is not a directory (is docs/drive linked, and offline?)")

    detected = lang or detect_language(node)
    S = STRINGS[detected]
    today = datetime.date.today()
    dest = os.path.join(node, "docs", "index.md")

    # A cell with no readable id keeps the link the index being replaced had for that
    # same path: this machine not reading ids is no reason to blank another machine's.
    before, linked, kept, unlinked = previous_links(dest), [], [], []

    def link(path, url):
        if not url:
            url = before.get(nfc(path), "")
            (kept if url else unlinked).append(path)
        if url:
            linked.append(path)
        return url

    groups, pointers, total, count = {}, [], 0, 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel = os.path.relpath(dirpath, root)
        rel = "" if rel == "." else rel
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            ext = pathlib.Path(fn).suffix.lower()
            size = os.path.getsize(os.path.join(dirpath, fn))
            count += 1
            path = os.path.join(rel, fn) if rel else fn
            if ext in POINTERS:
                pointers.append((path, POINTERS[ext],
                                 link(path, pointer_link(os.path.join(dirpath, fn)))))
                continue
            total += size
            # The root is keyed "", which no folder can be named: a folder called
            # "(root)" keeps its own heading, and no file is listed under the wrong one.
            groups.setdefault(rel, []).append(
                (fn, size, ext, path, os.path.join(dirpath, fn)))

    out = [
        "---", "type: note", f"domain: {domain_of(node)}",
        f"date: {today}",
        "tags: [index, generated]", "---", "",
        S["title"].format(node=node), "",
        S["generated"].format(node=node), "",
        S["summary"].format(count=count, size=human(total), date=today), "",
    ]
    for folder in sorted(groups, key=lambda f: f or S["root_key"]):
        files = groups[folder]
        sub = sum(s for _, s, *_ in files)
        out += [f"## `{folder}/`" if folder else S["root_head"], "",
                S["folder_sub"].format(n=len(files), size=human(sub)), ""]
        if len(files) > COLLAPSE_OVER:
            # too many to list one by one -- summarise by type
            byext = {}
            for fn, size, ext, *_ in files:
                e = ext.lstrip(".") or "—"
                n, s = byext.get(e, (0, 0))
                byext[e] = (n + 1, s + size)
            out += [S["collapsed"], "", S["th_type"], "|---|---|---|"]
            for e in sorted(byext, key=lambda k: -byext[k][1]):
                n, s = byext[e]
                out.append(f"| {e} | {n} | {human(s)} |")
        else:
            # Ids are read only for files listed one by one: a collapsed folder has no cells.
            out += [S["th_file"], "|---|---|---|---|"]
            for fn, size, ext, path, full in files:
                url = link(path, file_link(full))
                row = f"| `{fn}` | {ext.lstrip('.') or '—'} | {human(size)} |"
                out.append(f"{row} {link_cell(url)} |" if url else f"{row} |")
        out.append("")

    # Pointers deliberately left as Google files are listed in docs/pointers-ok.md.
    # Without this, the warning cries wolf forever and stops being read.
    okfile = pathlib.Path(node) / "docs" / "pointers-ok.md"
    acked = set()
    if okfile.exists():
        acked = set(re.findall(r"`([^`]+)`", okfile.read_text(encoding="utf-8")))

    todo = [p for p in pointers if p[0] not in acked]
    ok   = [p for p in pointers if p[0] in acked]

    if todo:
        out += [S["ptr_head"], ""] + S["ptr_body"] + ["", S["ptr_th"], "|---|---|---|"]
        for f, kind, url in sorted(todo):
            out.append(f"| `{f}` | {kind} | {link_cell(url)} |")
        out.append("")
    if ok:
        # Listed, not just counted: accepted pointers are the files notes link to.
        out += [S["ptr_ok"].format(n=len(ok)), "", S["ptr_ok_sub"], "",
                S["ptr_th"], "|---|---|---|"]
        for f, kind, url in sorted(ok):
            out.append(f"| `{f}` | {kind} | {link_cell(url)} |")
        out.append("")

    # --- guard: files parked in docs/ but not under docs/drive/ ---
    # gitignored by **/docs/*, and outside the symlink, so in NEITHER git NOR cloud.
    orphans, orphan_bytes = [], 0
    docs_dir = os.path.join(node, "docs")
    if os.path.isdir(docs_dir):
        for dp, dn, fns in os.walk(docs_dir):
            dn[:] = [d for d in dn if d != "drive" and not d.startswith(".")]
            if os.path.basename(dp) == "drive":
                continue
            for fn in fns:
                if fn.startswith(".") or fn.endswith(".md") or fn == "drive":
                    continue
                fp = os.path.join(dp, fn)
                # a dangling symlink (e.g. docs/drive seen from the agent bridge,
                # where /Users paths are not mounted) is not an orphan
                if os.path.islink(fp) or not os.path.isfile(fp):
                    continue
                orphans.append(os.path.relpath(fp, docs_dir))
                orphan_bytes += os.path.getsize(fp)

    if orphans:
        out += [S["orph_head"], "",
                S["orph_lead"].format(n=len(orphans), size=human(orphan_bytes)), ""] \
               + S["orph_bul"] + ["", S["orph_tail"], "", S["orph_th"], "|---|"]
        for o in sorted(orphans)[:15]:
            out.append(f"| `{o}` |")
        if len(orphans) > 15:
            out.append(S["orph_more"].format(n=len(orphans) - 15))
        out.append("")

    pathlib.Path(dest).write_text("\n".join(out), encoding="utf-8")
    how = "forced" if lang else "detected"
    print(f"wrote {dest} [{detected}, {how}]: {count} files, {len(todo)} pointers to "
          f"migrate ({len(ok)} accepted), {len(linked)} Drive link(s), {human(total)}")
    if kept:
        more = f", and {len(kept) - 5} more" if len(kept) > 5 else ""
        print(f"  WARNING: {len(kept)} link(s) kept from the previous index, not checked "
              f"here: no Drive id was readable for {', '.join(kept[:5])}{more}")
    if unlinked:
        print(f"  {len(unlinked)} file(s) had no readable Drive id and no earlier link; "
              f"their link cells are empty (ids come from Google pointer stubs and, on "
              f"macOS, from Drive for Desktop: is it running, the folder available offline?)")
    if orphans:
        print(f"  🚨 WARNING: {len(orphans)} orphan file(s) ({human(orphan_bytes)}) in "
              f"{docs_dir} are in NEITHER git NOR cloud storage — move them under docs/drive/")


main()
