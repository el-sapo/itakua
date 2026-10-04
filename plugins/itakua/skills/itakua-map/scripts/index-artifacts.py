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
exact. No other file does, and its cell stays EMPTY: a search by name can land on the
wrong copy, and a wrong link is worse than none. A pass over the Drive API could fill
those cells later, if it ever proves worth the credentials it needs. Folders collapsed
into a type summary list no files, so they have no cells to fill.
"""
import os, sys, datetime, json, pathlib, re

COLLAPSE_OVER = 12   # folders bigger than this are summarised by type
POINTERS = {".gdoc": "Google Doc", ".gsheet": "Google Sheet", ".gslides": "Google Slides"}
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{10,}")

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
            if ext in POINTERS:
                pointers.append((os.path.join(rel, fn) if rel else fn, POINTERS[ext],
                                 pointer_link(os.path.join(dirpath, fn))))
                continue
            total += size
            groups.setdefault(rel or S["root_key"], []).append((fn, size, ext))

    out = [
        "---", "type: note", f"domain: {domain_of(node)}",
        f"date: {today}",
        "tags: [index, generated]", "---", "",
        S["title"].format(node=node), "",
        S["generated"].format(node=node), "",
        S["summary"].format(count=count, size=human(total), date=today), "",
    ]
    for folder in sorted(groups):
        files = groups[folder]
        sub = sum(s for _, s, _ in files)
        out += [f"## `{folder}/`" if folder != S["root_key"] else S["root_head"], "",
                S["folder_sub"].format(n=len(files), size=human(sub)), ""]
        if len(files) > COLLAPSE_OVER:
            # too many to list one by one -- summarise by type
            byext = {}
            for fn, size, ext in files:
                e = ext.lstrip(".") or "—"
                n, s = byext.get(e, (0, 0))
                byext[e] = (n + 1, s + size)
            out += [S["collapsed"], "", S["th_type"], "|---|---|---|"]
            for e in sorted(byext, key=lambda k: -byext[k][1]):
                n, s = byext[e]
                out.append(f"| {e} | {n} | {human(s)} |")
        else:
            # No file id on disk outside pointer files: the link cell stays empty.
            out += [S["th_file"], "|---|---|---|---|"]
            for fn, size, ext in files:
                out.append(f"| `{fn}` | {ext.lstrip('.') or '—'} | {human(size)} | |")
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

    dest = os.path.join(node, "docs", "index.md")
    pathlib.Path(dest).write_text("\n".join(out), encoding="utf-8")
    how = "forced" if lang else "detected"
    linked = sum(1 for p in pointers if p[2])
    print(f"wrote {dest} [{detected}, {how}]: {count} files, {len(todo)} pointers to "
          f"migrate ({len(ok)} accepted), {linked} Drive link(s), {human(total)}")
    if linked < len(pointers):
        print(f"  {len(pointers) - linked} pointer(s) had no readable Drive id; their "
              f"link cells are empty (is the folder Available offline?)")
    if orphans:
        print(f"  🚨 WARNING: {len(orphans)} orphan file(s) ({human(orphan_bytes)}) in "
              f"{docs_dir} are in NEITHER git NOR cloud storage — move them under docs/drive/")


main()
