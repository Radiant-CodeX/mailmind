# -*- coding: utf-8 -*-
"""
MailMind — Complete Source Code PDF generator.

Produces a single, source-code-first PDF that reproduces the entire MailMind
application repository in full (zero truncation), with a cover page, page-
referenced table of contents, repository metadata, full directory tree, a
source-code index, the complete source of every text file (syntax highlighted,
line-numbered, hard-wrapped so nothing is clipped), plus structured reference
sections for configuration, database, API, AI/LLM and deployment.

Run from the repository root:
    python tools/build_source_pdf.py
"""

import os
import re
import subprocess
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    Flowable, PageBreak, NextPageTemplate, KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ──────────────────────────────────────────────────────────────────────────
# Paths & scope
# ──────────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "MailMind_Complete_Source_Code.pdf")

# The /video folder is the auxiliary Remotion marketing-video project, not part
# of the MailMind application — excluded from this source dump.
SCOPE_EXCLUDE_PREFIXES = ("video/",)

# ──────────────────────────────────────────────────────────────────────────
# Fonts
# ──────────────────────────────────────────────────────────────────────────
MONO, MONO_B = "Courier", "Courier-Bold"
for cand, bold in [
    (r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\consolab.ttf"),
    (r"C:\Windows\Fonts\cour.ttf", r"C:\Windows\Fonts\courbd.ttf"),
]:
    try:
        pdfmetrics.registerFont(TTFont("CodeMono", cand))
        pdfmetrics.registerFont(TTFont("CodeMono-Bold", bold))
        MONO, MONO_B = "CodeMono", "CodeMono-Bold"
        break
    except Exception:
        continue

UI = "Helvetica"
UI_B = "Helvetica-Bold"

# ──────────────────────────────────────────────────────────────────────────
# Palette
# ──────────────────────────────────────────────────────────────────────────
INK = colors.HexColor("#1f2328")
MUTED = colors.HexColor("#57606a")
ACCENT = colors.HexColor("#6366f1")
ACCENT2 = colors.HexColor("#0ea5e9")
PAGE_BG = colors.white
CODE_BG = colors.HexColor("#f6f8fa")
GUTTER = colors.HexColor("#8c959f")
RULE = colors.HexColor("#d0d7de")
HEADER_BAR = colors.HexColor("#eef0ff")

C_DEFAULT = colors.HexColor("#1f2328")
C_KEYWORD = colors.HexColor("#cf222e")
C_STRING = colors.HexColor("#0a3069")
C_COMMENT = colors.HexColor("#6e7781")
C_NUMBER = colors.HexColor("#0550ae")
C_DECOR = colors.HexColor("#8250df")

# ──────────────────────────────────────────────────────────────────────────
# Geometry
# ──────────────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
M_L, M_R, M_T, M_B = 38, 28, 40, 38
FRAME_W = PAGE_W - M_L - M_R
FRAME_H = PAGE_H - M_T - M_B

CODE_SIZE = 6.7
CODE_LEAD = 8.4
GUTTER_W = 30.0
CHARW = pdfmetrics.stringWidth("0", MONO, CODE_SIZE) or (CODE_SIZE * 0.6)
TEXT_W = FRAME_W - GUTTER_W
MAXCOL = max(40, int(TEXT_W / CHARW) - 1)

# ──────────────────────────────────────────────────────────────────────────
# Syntax highlighting
# ──────────────────────────────────────────────────────────────────────────
PY_KW = set((
    "def class return if elif else for while try except finally with as import "
    "from pass break continue lambda yield global nonlocal assert raise in is "
    "not and or None True False async await del self cls match case await "
    "print"
).split())
TS_KW = set((
    "const let var function return if else for while switch case break continue "
    "new class extends implements interface type enum import export default "
    "async await yield try catch finally throw typeof instanceof in of as public "
    "private protected readonly static get set void null undefined true false "
    "this super namespace declare keyof abstract"
).split())
SQL_KW = set((
    "select insert update delete create alter drop table index view from where "
    "join inner left right outer on group by order having limit values into set "
    "primary key foreign references not null default unique constraint add column "
    "and or as distinct cascade exists if begin commit"
).split())
SQL_KW |= set(k.upper() for k in SQL_KW)


def cfg_for(family):
    if family == "python":
        return dict(line="#", block=None, quotes=['"', "'"], triple=True, template=False, kw=PY_KW)
    if family == "ts":
        return dict(line="//", block=("/*", "*/"), quotes=['"', "'"], triple=False, template=True, kw=TS_KW)
    if family == "json":
        return dict(line=None, block=None, quotes=['"'], triple=False, template=False, kw={"true", "false", "null"})
    if family == "css":
        return dict(line=None, block=("/*", "*/"), quotes=['"', "'"], triple=False, template=False, kw=set())
    if family == "sql":
        return dict(line="--", block=("/*", "*/"), quotes=["'", '"'], triple=False, template=False, kw=SQL_KW)
    if family == "hash":
        return dict(line="#", block=None, quotes=['"', "'"], triple=False, template=False, kw=set())
    return dict(line=None, block=None, quotes=[], triple=False, template=False, kw=set())


def hl_line(line, cfg, state):
    """Highlight one physical source line. Returns (segments, new_state)."""
    n = len(line)
    i = 0
    segs = []

    def add(t, c):
        if not t:
            return
        if segs and segs[-1][1] == c:
            segs[-1] = (segs[-1][0] + t, c)
        else:
            segs.append((t, c))

    # Resume a carried multi-line construct from the previous line.
    if state == "block":
        e = line.find(cfg["block"][1])
        if e == -1:
            return ([(line, C_COMMENT)] if line else []), "block"
        end = e + len(cfg["block"][1])
        add(line[:end], C_COMMENT)
        i = end
        state = None
    elif isinstance(state, tuple) and state[0] == "tri":
        q = state[1]
        e = line.find(q)
        if e == -1:
            return ([(line, C_STRING)] if line else []), state
        add(line[: e + 3], C_STRING)
        i = e + 3
        state = None
    elif state == "tmpl":
        j = i
        while j < n:
            if line[j] == "\\":
                j += 2
                continue
            if line[j] == "`":
                break
            j += 1
        if j >= n:
            add(line[i:], C_STRING)
            return segs, "tmpl"
        add(line[i : j + 1], C_STRING)
        i = j + 1
        state = None

    while i < n:
        ch = line[i]
        if cfg["line"] and line.startswith(cfg["line"], i):
            add(line[i:], C_COMMENT)
            i = n
            break
        if cfg["block"] and line.startswith(cfg["block"][0], i):
            e = line.find(cfg["block"][1], i + len(cfg["block"][0]))
            if e == -1:
                add(line[i:], C_COMMENT)
                return segs, "block"
            end = e + len(cfg["block"][1])
            add(line[i:end], C_COMMENT)
            i = end
            continue
        if cfg["triple"] and (line.startswith('"""', i) or line.startswith("'''", i)):
            q = line[i : i + 3]
            e = line.find(q, i + 3)
            if e == -1:
                add(line[i:], C_STRING)
                return segs, ("tri", q)
            add(line[i : e + 3], C_STRING)
            i = e + 3
            continue
        if cfg["template"] and ch == "`":
            j = i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == "`":
                    break
                j += 1
            if j >= n:
                add(line[i:], C_STRING)
                return segs, "tmpl"
            add(line[i : j + 1], C_STRING)
            i = j + 1
            continue
        if ch in cfg["quotes"]:
            j = i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == ch:
                    break
                j += 1
            if j >= n:
                add(line[i:], C_STRING)
                i = n
                break
            add(line[i : j + 1], C_STRING)
            i = j + 1
            continue
        if ch == "@" and cfg["triple"]:
            j = i + 1
            while j < n and (line[j].isalnum() or line[j] in "_."):
                j += 1
            add(line[i:j], C_DECOR)
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (line[j].isalnum() or line[j] == "_"):
                j += 1
            word = line[i:j]
            add(word, C_KEYWORD if word in cfg["kw"] else C_DEFAULT)
            i = j
            continue
        if ch.isdigit():
            j = i + 1
            while j < n and (line[j].isalnum() or line[j] == "."):
                j += 1
            add(line[i:j], C_NUMBER)
            i = j
            continue
        add(ch, C_DEFAULT)
        i += 1

    return segs, None


def highlight(text, family):
    cfg = cfg_for(family)
    out = []
    state = None
    for line in text.split("\n"):
        segs, state = hl_line(line, cfg, state)
        out.append(segs)
    return out


def wrap_segments(segs, maxcol):
    """Hard-wrap a line's colored segments to <= maxcol columns. No truncation."""
    lines = []
    cur = []
    curlen = 0
    for text, color in segs:
        while text:
            room = maxcol - curlen
            if len(text) <= room:
                cur.append((text, color))
                curlen += len(text)
                text = ""
            else:
                if room > 0:
                    cur.append((text[:room], color))
                    text = text[room:]
                lines.append(cur)
                cur = []
                curlen = 0
    lines.append(cur)
    return lines or [[]]


# ──────────────────────────────────────────────────────────────────────────
# Code flowable (paginating, monospace, line-numbered)
# ──────────────────────────────────────────────────────────────────────────
class CodeBlock(Flowable):
    def __init__(self, plines):
        Flowable.__init__(self)
        self.plines = plines  # list of (label:str, segments:list[(text,color)])
        self.width = FRAME_W

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, len(self.plines) * CODE_LEAD

    def split(self, availWidth, availHeight):
        maxlines = int(availHeight / CODE_LEAD)
        if maxlines <= 0:
            return []
        if maxlines >= len(self.plines):
            return [self]
        return [CodeBlock(self.plines[:maxlines]), CodeBlock(self.plines[maxlines:])]

    def draw(self):
        c = self.canv
        n = len(self.plines)
        h = n * CODE_LEAD
        # background + gutter rule + accent bar
        c.setFillColor(CODE_BG)
        c.rect(0, 0, self.width, h, stroke=0, fill=1)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.line(GUTTER_W - 4, 0, GUTTER_W - 4, h)
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.2)
        c.line(0.6, 0, 0.6, h)
        c.setFont(MONO, CODE_SIZE)
        for idx, (label, segs) in enumerate(self.plines):
            y = h - (idx + 1) * CODE_LEAD + 2.0
            if label:
                c.setFillColor(GUTTER)
                c.drawRightString(GUTTER_W - 7, y, label)
            col = 0
            for text, color in segs:
                if text.strip() == "" and len(text) == 0:
                    continue
                c.setFillColor(color)
                c.drawString(GUTTER_W + col * CHARW, y, text)
                col += len(text)


def code_plines(text, family):
    """Highlight + wrap a file's text into physical (label, segments) lines."""
    logical = highlight(text, family)
    plines = []
    for lineno, segs in enumerate(logical, start=1):
        wrapped = wrap_segments(segs, MAXCOL)
        for k, w in enumerate(wrapped):
            plines.append((str(lineno) if k == 0 else "", w))
    return plines


def code_flowables(text, family, chunk=110):
    """Build paginating CodeBlock flowables for a file's text."""
    plines = code_plines(text, family)
    blocks = [CodeBlock(plines[i : i + chunk]) for i in range(0, len(plines), chunk)]
    return blocks or [CodeBlock([("1", [])])]


# ──────────────────────────────────────────────────────────────────────────
# Styles
# ──────────────────────────────────────────────────────────────────────────
def S(name, **kw):
    base = dict(fontName=UI, fontSize=9.5, leading=13, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


ST = {
    "cover_title": S("cover_title", fontName=UI_B, fontSize=46, leading=50, textColor=ACCENT, alignment=TA_CENTER),
    "cover_sub": S("cover_sub", fontSize=15, leading=20, textColor=INK, alignment=TA_CENTER),
    "cover_small": S("cover_small", fontSize=10.5, leading=15, textColor=MUTED, alignment=TA_CENTER),
    "cover_label": S("cover_label", fontName=UI_B, fontSize=11, leading=15, textColor=ACCENT, alignment=TA_CENTER),
    "SectionH": S("SectionH", fontName=UI_B, fontSize=18, leading=22, textColor=ACCENT, spaceBefore=6, spaceAfter=10),
    "GroupH": S("GroupH", fontName=UI_B, fontSize=13, leading=17, textColor=ACCENT2, spaceBefore=10, spaceAfter=6),
    "FileH": S("FileH", fontName=UI_B, fontSize=10.5, leading=14, textColor=INK),
    "meta": S("meta", fontSize=8.2, leading=11, textColor=MUTED),
    "metab": S("metab", fontName=UI_B, fontSize=8.2, leading=11, textColor=INK),
    "body": S("body", fontSize=9.5, leading=13.5),
    "small": S("small", fontSize=8.3, leading=11.5, textColor=MUTED),
    "cell": S("cell", fontSize=7.6, leading=9.8),
    "cellb": S("cellb", fontName=UI_B, fontSize=7.6, leading=9.8, textColor=colors.white),
    "code_path": S("code_path", fontName=MONO, fontSize=7.6, leading=9.8, textColor=INK),
    "h_note": S("h_note", fontSize=9, leading=13, textColor=MUTED),
}

TOC_L0 = ParagraphStyle("TOC0", fontName=UI_B, fontSize=10.5, leading=16, textColor=INK)
TOC_L1 = ParagraphStyle("TOC1", fontName=MONO, fontSize=7.8, leading=11.5, textColor=MUTED, leftIndent=14)


# ──────────────────────────────────────────────────────────────────────────
# File model
# ──────────────────────────────────────────────────────────────────────────
LANGS = {
    "py": "Python", "ts": "TypeScript", "tsx": "TypeScript (TSX)", "js": "JavaScript",
    "mjs": "JavaScript (ESM)", "jsx": "JavaScript (JSX)", "sql": "SQL", "css": "CSS",
    "md": "Markdown", "json": "JSON", "yml": "YAML", "yaml": "YAML", "toml": "TOML",
    "ini": "INI", "txt": "Text", "example": "Env Example", "svg": "SVG",
}
FAMILY = {
    "py": "python", "ts": "ts", "tsx": "ts", "js": "ts", "mjs": "ts", "jsx": "ts",
    "json": "json", "css": "css", "sql": "sql",
    "yml": "hash", "yaml": "hash", "toml": "hash", "ini": "hash", "example": "hash",
}
BINARY_EXT = {"pckl", "pdf", "ico", "png", "jpg", "jpeg", "gif", "webp", "woff",
              "woff2", "ttf", "otf", "eot", "mp3", "mp4", "wav", "zip", "pyc"}

SPECIAL = {
    "Dockerfile": ("Dockerfile", "hash"),
    "Procfile": ("Procfile", "hash"),
    ".gitignore": ("Git Ignore", "hash"),
    ".dockerignore": ("Docker Ignore", "hash"),
    "Implementation and what Presidio does": ("Text", "plain"),
}


def classify(path):
    """Return (kind, lang, family). kind in {text, asset, data}."""
    name = os.path.basename(path)
    if name in SPECIAL:
        lang, fam = SPECIAL[name]
        return "text", lang, fam
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "svg":
        return "asset", "SVG", "plain"
    if ext in BINARY_EXT:
        return "asset", ext.upper(), "plain"
    # generated / runtime data artifacts (kept out of the dump, listed instead)
    if path.startswith("backend/data/") or path.startswith("backend/.langgraph_api/"):
        return "data", LANGS.get(ext, "Data"), "plain"
    if path in ("backend/feedback_store.json", "backend/tests/eval/eval_report.json"):
        return "data", "JSON", "plain"
    lang = LANGS.get(ext, "Text")
    fam = FAMILY.get(ext, "plain")
    return "text", lang, fam


def home_section(path):
    name = os.path.basename(path)
    if (path.startswith(".github/") or path.startswith("infra/")
            or name in ("Procfile", "railway.toml", ".dockerignore")
            or name.startswith("docker-compose") or "Dockerfile" in name):
        return "deploy"
    if (name in ("package.json", "package-lock.json", "tsconfig.json", "pyproject.toml",
                 "ruff.toml", "langgraph.json", "requirements.txt", "requirements-prod.txt",
                 "postcss.config.mjs", "eslint.config.mjs", "next.config.ts",
                 "vitest.config.ts", ".gitignore")
            or name.endswith(".example")):
        return "config"
    return "source"


def read_text(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        raw = f.read()
    txt = raw.decode("utf-8", errors="replace")
    if txt and txt[0] == "﻿":
        txt = txt[1:]
    return txt.replace("\r\n", "\n").replace("\r", "\n")


PURPOSE_HEURISTIC = [
    ("backend/app/api/", "FastAPI route handlers exposing MailMind's HTTP API."),
    ("backend/app/services/", "Service-layer business logic."),
    ("backend/app/graph/", "LangGraph agentic pipeline definition and state."),
    ("backend/app/agents/", "LangGraph agent node implementations."),
    ("backend/app/tools/", "Agent tool implementations."),
    ("backend/app/db/", "Database models / persistence layer."),
    ("backend/app/models", "Pydantic / ORM data schemas."),
    ("backend/app/monitoring/", "Runtime metrics and monitoring."),
    ("backend/app/queue/", "Background enrichment queue backends."),
    ("backend/app/workers/", "Background worker logic."),
    ("backend/app/config/", "Application configuration and secrets."),
    ("backend/scripts/", "Operational / maintenance script."),
    ("backend/tests/", "Automated backend tests."),
    ("frontend/components/", "React UI component."),
    ("frontend/hooks/", "React hook."),
    ("frontend/lib/", "Frontend client library / utility."),
    ("frontend/app/", "Next.js route, layout or page."),
    ("docs/", "Project documentation."),
]


def extract_purpose(path, text, lang):
    t = text.lstrip()
    if lang.startswith("Python"):
        m = re.match(r'(?:#![^\n]*\n)?(?:#[^\n]*\n|\s*\n)*("""|\'\'\')(.*?)\1', text, re.S)
        if m:
            doc = m.group(2).strip().split("\n")[0].strip()
            if doc:
                return doc[:240]
    if lang.startswith(("TypeScript", "JavaScript")):
        m = re.match(r"\s*/\*+(.*?)\*/", text, re.S)
        if m:
            doc = re.sub(r"^\s*\*", "", m.group(1).strip(), flags=re.M).strip().split("\n")[0].strip()
            if doc:
                return doc[:240]
        m = re.match(r"\s*(?://[^\n]*\n)+", text)
        if m:
            doc = re.sub(r"^\s*//", "", m.group(0).strip().split("\n")[0]).strip()
            if doc and not doc.lower().startswith(("use client", "use server", "eslint")):
                return doc[:240]
    if lang == "Markdown":
        for line in text.split("\n"):
            s = line.strip().lstrip("#").strip()
            if s:
                return s[:240]
    for prefix, desc in PURPOSE_HEURISTIC:
        if path.startswith(prefix):
            return desc
    return "Repository file."


def extract_deps(path, text, lang):
    deps = []
    if lang.startswith("Python"):
        for m in re.finditer(r"^\s*from\s+([.\w]+)\s+import|^\s*import\s+([\w.]+)", text, re.M):
            deps.append((m.group(1) or m.group(2)).split(".")[0] if not (m.group(1) or "").startswith(".") else (m.group(1) or m.group(2)))
    elif lang.startswith(("TypeScript", "JavaScript")):
        for m in re.finditer(r"""(?:from|import|require\()\s*['"]([^'"]+)['"]""", text):
            deps.append(m.group(1))
    seen, out = set(), []
    for d in deps:
        d = d.strip()
        if d and d not in seen:
            seen.add(d)
            out.append(d)
        if len(out) >= 22:
            break
    return ", ".join(out) if out else "—"


# ──────────────────────────────────────────────────────────────────────────
# Gather repository
# ──────────────────────────────────────────────────────────────────────────
def git(*args, default=""):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL).decode("utf-8", "replace").strip()
    except Exception:
        return default


def gather():
    listing = git("ls-files").split("\n")
    files = []
    for p in listing:
        p = p.strip().replace("\\", "/")
        if not p or any(p.startswith(x) for x in SCOPE_EXCLUDE_PREFIXES):
            continue
        kind, lang, fam = classify(p)
        rec = {"path": p, "kind": kind, "lang": lang, "family": fam,
               "section": home_section(p) if kind == "text" else None, "lines": 0}
        if kind == "text":
            try:
                rec["text"] = read_text(p)
                rec["lines"] = rec["text"].count("\n") + (0 if rec["text"].endswith("\n") else 1) if rec["text"] else 0
            except Exception as e:
                rec["text"] = f"<<unreadable: {e}>>"
        files.append(rec)
    return files


# ──────────────────────────────────────────────────────────────────────────
# Repository tree
# ──────────────────────────────────────────────────────────────────────────
def build_tree(paths):
    root = {}
    for p in sorted(paths):
        parts = p.split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault("__files__", []).append(parts[-1])

    out = []

    def walk(node, prefix=""):
        dirs = sorted([k for k in node.keys() if k != "__files__"])
        fileitems = sorted(node.get("__files__", []))
        entries = [(d, True) for d in dirs] + [(f, False) for f in fileitems]
        for i, (name, is_dir) in enumerate(entries):
            last = i == len(entries) - 1
            branch = "└── " if last else "├── "
            out.append(prefix + branch + name + ("/" if is_dir else ""))
            if is_dir:
                walk(node[name], prefix + ("    " if last else "│   "))

    out.append("mailmind/")
    walk(root, "")
    return "\n".join(out)


# ──────────────────────────────────────────────────────────────────────────
# Extractors for reference sections (API, DB, AI)
# ──────────────────────────────────────────────────────────────────────────
def extract_routes(files):
    rows = []
    for rec in files:
        if not rec["path"].startswith("backend/app/api/") or not rec["path"].endswith(".py"):
            continue
        text = rec.get("text", "")
        lines = text.split("\n")
        prefix = ""
        m = re.search(r"APIRouter\([^)]*prefix\s*=\s*['\"]([^'\"]*)['\"]", text)
        if m:
            prefix = m.group(1)
        for idx, line in enumerate(lines):
            dm = re.search(r"@\w+\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]", line)
            if not dm:
                continue
            method = dm.group(1).upper()
            route = (prefix + dm.group(2)) if not dm.group(2).startswith(prefix) else dm.group(2)
            handler, auth = "—", "—"
            for j in range(idx + 1, min(idx + 8, len(lines))):
                hm = re.search(r"def\s+(\w+)\s*\(", lines[j])
                if hm:
                    handler = hm.group(1)
                    sig = " ".join(lines[j:min(j + 10, len(lines))])
                    if re.search(r"Depends\(|current_user|require_|get_current|session", sig):
                        auth = "Required"
                    break
            rows.append((method, route, auth, handler, rec["path"]))
    return rows


def extract_models(files):
    rec = next((r for r in files if r["path"] == "backend/app/db/models.py"), None)
    if not rec:
        return []
    text = rec.get("text", "")
    lines = text.split("\n")
    tables = []
    cur = None
    for line in lines:
        cm = re.match(r"\s*class\s+(\w+)\s*\(\s*Base\s*\)", line)
        if cm:
            cur = {"model": cm.group(1), "table": "", "cols": [], "rels": []}
            tables.append(cur)
            continue
        if cur is None:
            continue
        tm = re.search(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", line)
        if tm:
            cur["table"] = tm.group(1)
            continue
        col = re.match(r"\s*(\w+)\s*:\s*Mapped\[([^\]]+)\]\s*=\s*mapped_column\((.*)", line)
        if col:
            flags = []
            body = col.group(3)
            if "primary_key=True" in body:
                flags.append("PK")
            if "ForeignKey(" in body:
                fk = re.search(r"ForeignKey\(\s*['\"]([^'\"]+)['\"]", body)
                flags.append("FK→" + fk.group(1) if fk else "FK")
            if "unique=True" in body:
                flags.append("unique")
            if "index=True" in body:
                flags.append("index")
            cur["cols"].append((col.group(1), col.group(2).strip(), " ".join(flags)))
            continue
        rel = re.match(r"\s*(\w+)\s*:\s*Mapped\[[^\]]+\]\s*=\s*relationship\(", line)
        if rel:
            cur["rels"].append(rel.group(1))
    return tables


AI_KEYWORDS = ["prompt", "agent", "node", "graph", "pipeline", "triage", "scorer",
               "rag", "draft", "tone_dna", "classif", "commit", "retriev", "eval",
               "llm", "tools", "calendar", "pii"]


def extract_ai(files):
    rows = []
    for rec in files:
        p = rec["path"]
        if rec["kind"] != "text" or not p.startswith("backend/"):
            continue
        low = p.lower()
        if any(k in low for k in AI_KEYWORDS) and p.endswith(".py"):
            rows.append((p, extract_purpose(p, rec.get("text", ""), rec["lang"])))
    # dedupe preserve order
    seen, out = set(), []
    for p, d in rows:
        if p not in seen:
            seen.add(p)
            out.append((p, d))
    return out


# ──────────────────────────────────────────────────────────────────────────
# Cover artwork — the real MailMind monogram + brand styling
# ──────────────────────────────────────────────────────────────────────────
# Three slashes forming an "M", taken verbatim from frontend/public/mailmind-logo.svg
# (viewBox 0 0 500 500). Each entry is a closed polygon.
LOGO_POLYS = [
    [(217.139, 198.5), (128.997, 352.993), (99.0771, 301.0), (158.289, 198.5)],
    [(293.132, 198.5), (241.503, 287.497), (212.078, 236.004), (234.285, 198.5)],
    [(399.139, 150.5), (310.994, 304.999), (280.578, 252.999), (340.287, 150.5)],
]

COVER_TOP = colors.HexColor("#090b16")
COVER_BOT = colors.HexColor("#0e1226")
COVER_CYAN = colors.HexColor("#38e0e0")
COVER_INDIGO = colors.HexColor("#818cf8")
COVER_VIOLET = colors.HexColor("#a78bfa")


def draw_logo(c, cx, cy, size):
    """Render the MailMind monogram centred at (cx, cy), gradient-filled with a glow."""
    scale = size / 500.0
    ox, oy = cx - size / 2.0, cy - size / 2.0

    # Soft radial glow behind the mark.
    c.saveState()
    for i in range(16, 0, -1):
        c.setFillColor(COVER_VIOLET if i % 2 else COVER_INDIGO)
        c.setFillAlpha(0.05 * (i / 16.0))
        c.circle(cx, cy, size * 0.28 + i * (size * 0.04), stroke=0, fill=1)
    c.setFillAlpha(1)
    c.restoreState()

    # Build the union of the three slashes as one clip region, fill with a
    # diagonal cyan → indigo → violet gradient.
    c.saveState()
    p = c.beginPath()
    for poly in LOGO_POLYS:
        first = True
        for (x, y) in poly:
            X = ox + x * scale
            Y = oy + (500.0 - y) * scale  # flip SVG (top-down) to PDF (bottom-up)
            if first:
                p.moveTo(X, Y)
                first = False
            else:
                p.lineTo(X, Y)
        p.close()
    c.clipPath(p, stroke=0, fill=0)
    c.linearGradient(ox, oy, ox + size, oy + size,
                     (COVER_CYAN, COVER_INDIGO, COVER_VIOLET), (0.0, 0.5, 1.0), extend=True)
    c.restoreState()


def hairline_gradient(c, y, h=3):
    """A full-width cyan→violet accent hairline at height y."""
    c.saveState()
    path = c.beginPath()
    path.rect(0, y, PAGE_W, h)
    c.clipPath(path, stroke=0, fill=0)
    c.linearGradient(0, y, PAGE_W, y, (COVER_CYAN, COVER_INDIGO, COVER_VIOLET), (0.0, 0.5, 1.0), extend=True)
    c.restoreState()


# ──────────────────────────────────────────────────────────────────────────
# Document template (TOC + footer + outline)
# ──────────────────────────────────────────────────────────────────────────
class DocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kw):
        BaseDocTemplate.__init__(self, filename, **kw)
        cover = PageTemplate(id="cover", frames=[Frame(0, 0, PAGE_W, PAGE_H, id="c")],
                             onPage=self._draw_cover)
        body = PageTemplate(id="body", frames=[Frame(M_L, M_B, FRAME_W, FRAME_H, id="b",
                            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
                            onPage=self._footer)
        self.addPageTemplates([cover, body])
        self._key = 0

    def handle_documentBegin(self):
        self._key = 0
        BaseDocTemplate.handle_documentBegin(self)

    def _draw_cover(self, c, doc):
        meta = getattr(self, "_cover", {})
        cx = PAGE_W / 2.0

        # 1. Background vertical gradient.
        c.saveState()
        bg = c.beginPath()
        bg.rect(0, 0, PAGE_W, PAGE_H)
        c.clipPath(bg, stroke=0, fill=0)
        c.linearGradient(0, PAGE_H, 0, 0, (COVER_TOP, COVER_BOT), (0.0, 1.0), extend=True)
        c.restoreState()

        # faint vignette corners
        c.saveState()
        c.setFillColor(colors.black)
        for r, a in [(360, 0.05), (300, 0.05), (240, 0.05)]:
            c.setFillAlpha(a)
            c.circle(-40, PAGE_H + 40, r, stroke=0, fill=1)
            c.circle(PAGE_W + 40, -40, r, stroke=0, fill=1)
        c.setFillAlpha(1)
        c.restoreState()

        # 2. Top & bottom accent hairlines.
        hairline_gradient(c, PAGE_H - 5, 5)
        hairline_gradient(c, 0, 5)

        # 2b. Faint inset frame so the negative space reads as intentional.
        c.saveState()
        c.setStrokeColor(colors.HexColor("#2c3559"))
        c.setStrokeAlpha(0.55)
        c.setLineWidth(1.0)
        c.roundRect(26, 26, PAGE_W - 52, PAGE_H - 52, 12, stroke=1, fill=0)
        c.setStrokeAlpha(1)
        c.restoreState()

        # 3. Logo + glow.
        draw_logo(c, cx, PAGE_H - 232, 132)

        # 4. Wordmark — two-tone "Mail" (light) + "Mind" (violet).
        c.setFont(UI_B, 52)
        w1 = pdfmetrics.stringWidth("Mail", UI_B, 52)
        w2 = pdfmetrics.stringWidth("Mind", UI_B, 52)
        wx = cx - (w1 + w2) / 2.0
        wy = PAGE_H - 320
        c.setFillColor(colors.HexColor("#eef1ff"))
        c.drawString(wx, wy, "Mail")
        c.setFillColor(COVER_VIOLET)
        c.drawString(wx + w1, wy, "Mind")

        # 5. Subtitle.
        c.setFillColor(colors.HexColor("#aeb8e8"))
        c.setFont(UI, 15.5)
        c.drawCentredString(cx, PAGE_H - 348, "AI-Powered Email Intelligence Platform")

        # 6. Kicker (letter-spaced, manually centred to account for char spacing).
        def centered_spaced(text, y, font, size, cspace, color):
            c.setFont(font, size)
            c.setFillColor(color)
            widths = [pdfmetrics.stringWidth(ch, font, size) for ch in text]
            total = sum(widths) + cspace * (len(text) - 1)
            x = cx - total / 2.0
            for ch, w in zip(text, widths):
                c.drawString(x, y, ch)
                x += w + cspace

        centered_spaced("COMPLETE  SOURCE  CODE  REFERENCE", PAGE_H - 372, UI, 9.5, 3.2,
                        colors.HexColor("#6b73a6"))

        # 7. Divider.
        c.saveState()
        dp = c.beginPath()
        dp.rect(cx - 70, PAGE_H - 392, 140, 2)
        c.clipPath(dp, stroke=0, fill=0)
        c.linearGradient(cx - 70, 0, cx + 70, 0, (COVER_CYAN, COVER_VIOLET), (0.0, 1.0), extend=True)
        c.restoreState()

        # 8. Team.
        centered_spaced("PRESENTED BY TEAM RADIANTCODEX", PAGE_H - 432, UI_B, 10.5, 2.4, COVER_VIOLET)

        team = meta.get("team", [])
        y = PAGE_H - 466
        for name, role in team:
            c.setFillColor(colors.HexColor("#e7eaf6"))
            c.setFont(UI_B, 11)
            c.drawRightString(cx - 14, y, name)
            c.setFillColor(colors.HexColor("#8088b0"))
            c.setFont(UI, 11)
            c.drawString(cx + 14, y, role)
            y -= 23

        # 9. Footer metadata.
        c.setStrokeColor(colors.HexColor("#2a2f4a"))
        c.setLineWidth(0.6)
        c.line(cx - 150, 92, cx + 150, 92)
        c.setFillColor(colors.HexColor("#5b628c"))
        c.setFont(UI, 8.5)
        c.drawCentredString(cx, 76, meta.get("line1", ""))
        c.setFont(UI, 8)
        c.drawCentredString(cx, 62, meta.get("line2", ""))

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(M_L, M_B - 10, PAGE_W - M_R, M_B - 10)
        canvas.setFont(UI, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(M_L, M_B - 20, "MailMind — Complete Source Code Reference · Team RadiantCodeX")
        canvas.drawRightString(PAGE_W - M_R, M_B - 20, "Page %d" % doc.page)
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style = flowable.style.name
        if style not in ("SectionH", "FileH", "GroupH"):
            return
        text = flowable.getPlainText()
        self._key += 1
        key = "k%d" % self._key
        self.canv.bookmarkPage(key)
        if style == "SectionH":
            self.notify("TOCEntry", (0, text, self.page, key))
            self.canv.addOutlineEntry(text, key, level=0, closed=False)
        elif style == "GroupH":
            self.canv.addOutlineEntry(text, key, level=1, closed=True)
        elif style == "FileH":
            self.notify("TOCEntry", (1, text, self.page, key))
            self.canv.addOutlineEntry(text, key, level=1, closed=True)


# ──────────────────────────────────────────────────────────────────────────
# Building blocks
# ──────────────────────────────────────────────────────────────────────────
def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def hr(color=RULE, w=0.6, space=6):
    from reportlab.platypus import HRFlowable
    return HRFlowable(width="100%", thickness=w, color=color, spaceBefore=space, spaceAfter=space)


def section(story, title):
    story.append(PageBreak())
    story.append(Paragraph(esc(title), ST["SectionH"]))
    story.append(hr(ACCENT, 1.2, 4))


def file_entry(story, rec, index):
    path = rec["path"]
    purpose = extract_purpose(path, rec.get("text", ""), rec["lang"])
    deps = extract_deps(path, rec.get("text", ""), rec["lang"])
    header = [
        Paragraph("&#9656; " + esc(path), ST["FileH"]),
        Spacer(1, 1),
        Paragraph("<b>Language:</b> %s &nbsp;&nbsp; <b>Lines:</b> %d &nbsp;&nbsp; <b>Section file #%d</b>"
                  % (esc(rec["lang"]), rec["lines"], index), ST["meta"]),
        Paragraph("<b>Purpose:</b> " + esc(purpose), ST["meta"]),
        Paragraph("<b>Dependencies:</b> " + esc(deps), ST["meta"]),
        Spacer(1, 3),
    ]
    # Keep the header glued to a small first slice of code (fits a column); the
    # remainder flows freely across columns/pages.
    plines = code_plines(rec.get("text", ""), rec["family"])
    head, rest = plines[:8], plines[8:]
    story.append(KeepTogether(header + [CodeBlock(head)]))
    for i in range(0, len(rest), 100):
        story.append(CodeBlock(rest[i : i + 100]))
    story.append(Spacer(1, 4))


def kv_table(rows, col0=150):
    data = [[Paragraph("<b>%s</b>" % esc(k), ST["meta"]), Paragraph(esc(v), ST["meta"])] for k, v in rows]
    t = Table(data, colWidths=[col0, FRAME_W - col0])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (0, -1), HEADER_BAR),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def data_table(header, rows, widths, header_bg=ACCENT):
    data = [[Paragraph(esc(h), ST["cellb"]) for h in header]]
    for r in rows:
        data.append([Paragraph(esc(str(c)), ST["code_path"] if ci == 0 and len(str(c)) > 20 else ST["cell"]) for ci, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7fb")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


# ──────────────────────────────────────────────────────────────────────────
# Assemble
# ──────────────────────────────────────────────────────────────────────────
def build():
    all_files = gather()
    # Configuration and deployment/infrastructure files are excluded from this
    # document by request — this drops tsconfig, pyproject, lockfiles, Docker/compose,
    # CI workflows and infra config (no Section 5 / Section 9). The three key
    # dependency/environment manifests below are explicitly kept and reproduced.
    FORCE_INCLUDE = {"backend/requirements.txt", "frontend/package.json", "backend/.env.example"}
    for f in all_files:
        if f["path"] in FORCE_INCLUDE:
            f["section"] = "source"
    excluded_paths = {f["path"] for f in all_files
                      if f["kind"] == "text" and f["section"] in ("config", "deploy")}
    files = [f for f in all_files if f["path"] not in excluded_paths]
    text_files = [f for f in files if f["kind"] == "text"]
    assets = [f for f in files if f["kind"] == "asset"]
    data_files = [f for f in files if f["kind"] == "data"]

    total_loc = sum(f["lines"] for f in text_files)
    commit = git("rev-parse", "HEAD", default="(unknown)")
    short = git("rev-parse", "--short", "HEAD", default="")
    branch = git("rev-parse", "--abbrev-ref", "HEAD", default="main")
    remote = git("config", "--get", "remote.origin.url", default="https://github.com/Radiant-CodeX/mailmind.git")
    commit_msg = git("log", "-1", "--pretty=%s", default="")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    by_section = {"source": [], "config": [], "deploy": []}
    for f in text_files:
        by_section[f["section"]].append(f)
    for k in by_section:
        by_section[k].sort(key=lambda r: r["path"])

    langs_present = sorted(set(f["lang"] for f in text_files))
    frameworks = ("FastAPI · Starlette · Uvicorn/Gunicorn · SQLAlchemy 2.0 · Pydantic v2 · "
                  "LangGraph · LangChain · OpenAI / Azure OpenAI · Groq · Microsoft Presidio · "
                  "spaCy · scikit-learn · Redis · PostgreSQL (psycopg2) · MSAL · Sentry · "
                  "Next.js 16 · React 19 · Three.js · GSAP · TailwindCSS 4 · Vitest")

    team = [
        ("Tarunkumar S", "Product Lead & Solution Strategist"),
        ("Rithish Karthikeyan", "AI Workflow & Automation Lead"),
        ("Manish K", "LLM & Integrations Lead"),
        ("Rithish Barath N", "Full Stack & Experience Lead"),
        ("Shan Neeraj", "Enterprise & Security Lead"),
    ]
    cover_meta = {
        "team": team,
        "line1": "Generated %s   ·   commit %s   ·   branch %s" % (now, short or commit[:7], branch),
        "line2": remote,
    }

    story = []

    # ── COVER ── (fully drawn on the canvas in DocTemplate._draw_cover) ──
    story.append(Spacer(1, 2))
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ──────────────────────────────────────────────
    story.append(Paragraph("Table of Contents", ST["SectionH"]))
    story.append(hr(ACCENT, 1.2, 4))
    story.append(Paragraph("Sections are listed first; every reproduced source file is listed beneath "
                           "Section 4 with its exact page number for full traceability.", ST["small"]))
    story.append(Spacer(1, 6))
    toc = TableOfContents()
    toc.levelStyles = [TOC_L0, TOC_L1]
    story.append(toc)

    # ── SECTION 1 — REPOSITORY INFORMATION ─────────────────────────────
    section(story, "Section 1 — Repository Information")
    info = [
        ("Repository Name", "mailmind"),
        ("Repository URL", remote),
        ("Branch", branch),
        ("Latest Commit Hash", commit),
        ("Latest Commit Message", commit_msg),
        ("Generation Timestamp", now),
        ("Files in scope (this document)", str(len(files))),
        ("Source Files Reproduced", str(len(text_files))),
        ("Config / Deployment Files (excluded by request)", str(len(excluded_paths))),
        ("Binary / Asset Files (listed only)", str(len(assets))),
        ("Generated Data Files (listed only)", str(len(data_files))),
        ("Total Lines of Code (reproduced)", "{:,}".format(total_loc)),
        ("Languages Used", ", ".join(langs_present)),
        ("Frameworks Used", frameworks),
    ]
    story.append(kv_table(info))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>Scope &amp; methodology.</b> This document reproduces the full text of every "
        "application source and documentation file tracked by Git in the MailMind "
        "repository. <b>Most configuration and deployment/infrastructure files are excluded "
        "by request</b> — lockfiles (<font name='%s'>package-lock.json</font>), build/tooling "
        "config, Docker/Compose, CI workflows and infrastructure config — though the core "
        "dependency and environment manifests (<font name='%s'>requirements.txt</font>, "
        "<font name='%s'>package.json</font>, <font name='%s'>.env.example</font>) are reproduced "
        "in full. Binary artifacts (compiled pickles, icons, "
        "fonts), vector SVG diagram assets, and machine-generated runtime data cannot be "
        "meaningfully represented as text and are listed for completeness rather than dumped. "
        "The auxiliary Remotion marketing-video project under <font name='%s'>/video</font> is "
        "out of scope. Code is reproduced verbatim with original indentation, comments and "
        "formatting; long lines are hard-wrapped (never truncated) to fit the page."
        % (MONO, MONO, MONO, MONO, MONO),
        ST["body"]))

    # ── SECTION 2 — REPOSITORY STRUCTURE ───────────────────────────────
    section(story, "Section 2 — Repository Structure")
    story.append(Paragraph("Directory tree of the in-scope repository (configuration and "
                           "deployment files are omitted by request).", ST["small"]))
    story.append(Spacer(1, 4))
    tree = build_tree([f["path"] for f in files])
    for b in code_flowables(tree, "plain", chunk=120):
        story.append(b)

    # ── SECTION 3 — SOURCE CODE INDEX ──────────────────────────────────
    section(story, "Section 3 — Source Code Index")
    story.append(Paragraph("Every reproduced source file with its language and line count. "
                           "Page numbers for each file appear in the Table of Contents.", ST["small"]))
    story.append(Spacer(1, 4))
    idx_rows = [(f["path"], f["lang"], f["lines"]) for f in sorted(text_files, key=lambda r: r["path"])]
    story.append(data_table(["File Path", "Language", "Lines"], idx_rows,
                            [FRAME_W - 150, 95, 55]))
    if assets or data_files:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Excluded assets &amp; generated data (listed for completeness, not reproduced):", ST["metab"]))
        ex_rows = [(f["path"], f["lang"], "binary/asset" if f["kind"] == "asset" else "generated data")
                   for f in sorted(assets + data_files, key=lambda r: r["path"])]
        story.append(data_table(["File Path", "Type", "Reason"], ex_rows,
                                [FRAME_W - 180, 80, 100], header_bg=MUTED))

    # ── SECTION 4 — COMPLETE SOURCE CODE ───────────────────────────────
    section(story, "Section 4 — Complete Source Code")
    story.append(Paragraph("The complete, verbatim source of every application code and documentation "
                           "file in scope. Configuration and deployment/infrastructure files are "
                           "excluded by request, except the core dependency and environment "
                           "manifests. Each file shows its path, language, purpose and "
                           "dependencies, followed by its full line-numbered source.", ST["body"]))

    groups = [
        ("Project Manifests & Environment", lambda p: p in FORCE_INCLUDE),
        ("Backend — Application (backend/app)", lambda p: p.startswith("backend/app/")),
        ("Backend — Scripts, Migrations & Tests", lambda p: p.startswith("backend/") and not p.startswith("backend/app/")),
        ("Frontend — App Router (frontend/app)", lambda p: p.startswith("frontend/app/")),
        ("Frontend — Components", lambda p: p.startswith("frontend/components/")),
        ("Frontend — Hooks & Libraries", lambda p: p.startswith("frontend/hooks/") or p.startswith("frontend/lib/")),
        ("Frontend — Other", lambda p: p.startswith("frontend/") and not any(
            p.startswith(x) for x in ("frontend/app/", "frontend/components/", "frontend/hooks/", "frontend/lib/"))),
        ("Documentation & Root", lambda p: True),
    ]
    src_files = by_section["source"]
    consumed = set()
    counter = 0
    for gtitle, pred in groups:
        members = [f for f in src_files if f["path"] not in consumed and pred(f["path"])]
        if not members:
            continue
        story.append(Paragraph(esc(gtitle), ST["GroupH"]))
        story.append(hr(ACCENT2, 0.8, 2))
        for f in members:
            consumed.add(f["path"])
            counter += 1
            file_entry(story, f, counter)

    # ── SECTION 5 — DATABASE STRUCTURE ─────────────────────────────────
    section(story, "Section 5 — Database Structure")
    story.append(Paragraph("MailMind persists through SQLAlchemy 2.0 ORM models "
                           "(<font name='%s'>backend/app/db/models.py</font>). Full model source is in "
                           "Section 4; the tables below summarise the schema, relationships, keys and "
                           "indexes parsed directly from the models." % MONO, ST["body"]))
    tables = extract_models(files)
    if tables:
        story.append(Spacer(1, 6))
        story.append(Paragraph("ERD — Tables &amp; Relationships", ST["GroupH"]))
        erd_rows = [(t["table"] or "—", t["model"], str(len(t["cols"])),
                     ", ".join(t["rels"]) or "—") for t in tables]
        story.append(data_table(["Table", "Model Class", "Cols", "Relationships"], erd_rows,
                                [120, 120, 35, FRAME_W - 275]))
        for t in tables:
            story.append(Spacer(1, 8))
            story.append(Paragraph("Table <b>%s</b> &nbsp;(<font name='%s'>%s</font>)"
                                   % (esc(t["table"] or "?"), MONO, esc(t["model"])), ST["metab"]))
            crows = [(c[0], c[1], c[2] or "—") for c in t["cols"]]
            if crows:
                story.append(data_table(["Column", "Type (Mapped)", "Keys / Flags"], crows,
                                        [120, FRAME_W - 270, 150], header_bg=ACCENT2))
    # ── SECTION 6 — API REFERENCE ──────────────────────────────────────
    section(story, "Section 6 — API Reference")
    story.append(Paragraph("Every HTTP endpoint exposed by the FastAPI backend, parsed from the route "
                           "decorators. Handler source (request/response models, service calls) is "
                           "reproduced in full in the listed source file in Section 4.", ST["body"]))
    routes = extract_routes(files)
    story.append(Spacer(1, 6))
    story.append(Paragraph("%d endpoints across %d route modules." %
                           (len(routes), len(set(r[4] for r in routes))), ST["metab"]))
    story.append(Spacer(1, 4))
    story.append(data_table(["Method", "Route", "Auth", "Handler", "Source File"],
                            [(m, r, a, h, sf) for (m, r, a, h, sf) in routes],
                            [44, FRAME_W - 44 - 52 - 95 - 150, 52, 95, 150]))

    # ── SECTION 7 — AI / LLM IMPLEMENTATION ────────────────────────────
    section(story, "Section 7 — AI / LLM Implementation")
    story.append(Paragraph("MailMind's intelligence is a LangGraph pipeline: PII masking → commitment "
                           "extraction → calendar-conflict detection → thread &amp; RAG retrieval → "
                           "five-axis triage → tone-matched draft generation. The files implementing each "
                           "concern are listed below; their complete source (prompts, agent logic, "
                           "scorers, retrieval, orchestration and evaluation) is reproduced in full in "
                           "Section 4. The golden evaluation dataset is "
                           "<font name='%s'>backend/golden_dataset.json</font>." % MONO, ST["body"]))
    ai_rows = extract_ai(files)
    story.append(Spacer(1, 6))
    story.append(data_table(["AI / LLM Source File", "Purpose"], ai_rows,
                            [FRAME_W * 0.42, FRAME_W * 0.58]))

    # ── SECTION 8 — GITHUB REPOSITORY ──────────────────────────────────
    section(story, "Section 8 — GitHub Repository")
    story.append(kv_table([
        ("Repository URL", remote),
        ("Clone Command", "git clone " + remote),
        ("Branch", branch),
        ("Latest Commit", commit),
        ("Checkout", "git checkout %s && git reset --hard %s" % (branch, short or commit[:7])),
    ]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("This PDF reproduces every text-based file required to understand and rebuild "
                           "the MailMind application. Binary assets and generated data (Section 3) must be "
                           "regenerated or pulled from the repository.", ST["small"]))

    doc = DocTemplate(OUTPUT, pagesize=A4, title="MailMind — Complete Source Code",
                      author="Team RadiantCodeX")
    doc._cover = cover_meta
    print("Building PDF: %d files, %s LOC, maxcol=%d ..." % (len(text_files), "{:,}".format(total_loc), MAXCOL))
    doc.multiBuild(story)
    print("Wrote", OUTPUT, "(%.1f MB)" % (os.path.getsize(OUTPUT) / 1e6))


if __name__ == "__main__":
    build()
