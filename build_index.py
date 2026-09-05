#!/usr/bin/env python3
"""Build a self-contained search index page over the bloggen blogposts/ tree.

Scans every published post (`blogposts/<slug>/index.html` plus the legacy loose
`blogposts/blogpost_*.html` files), pulls title / headings / description / full
body text out of each one, and writes a single static page at
`blogposts/index.html` that links to all of them.

The page carries the whole corpus inline (~0.6 MB of text for ~80 posts) and
does BM25F ranking client-side over four weighted fields — title, headings,
description, body — so search works from `file://` with no server and no
network. Re-run after publishing new posts; the page is fully regenerated.

Deliberately stdlib-only and standalone, like publish.py: it must keep working
without google.generativeai, a GEMINI_API_KEY, or any pip install.

Usage:
    build_index.py [--open] [--out PATH] [--quiet]
"""

import argparse
import datetime
import glob
import hashlib
import html
import json
import os
import re
import sys
import webbrowser
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import provenance  # noqa: E402  — sibling module, needs the script dir on sys.path

# --- kept in sync with main.py / publish.py ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLOGPOST_DIR = os.path.join(SCRIPT_DIR, "blogposts")
BROWSER_PATH = os.getenv("BROWSER_PATH", "/usr/bin/firefox")

INDEX_NAME = "index.html"          # generated page, at the root of blogposts/
TEMPLATE = os.path.join(SCRIPT_DIR, "assets", "index_template.html")

# Slug prefixes too generic to be worth a series chip.
SERIES_STOPLIST = {"blogpost", "content", "post", "screenshot", "pasted"}
SERIES_MIN = 3

try:
    from termcolor import colored
except ImportError:  # keep the tool usable without termcolor
    def colored(text, *_args, **_kwargs):
        return text


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #

class PostParser(HTMLParser):
    """Pull visible text, headings and paragraphs out of a published post."""

    SKIP = {"script", "style", "noscript", "head", "svg", "template"}
    BLOCK = {
        "p", "div", "section", "article", "header", "footer", "main", "aside",
        "li", "tr", "td", "th", "pre", "blockquote", "figcaption", "dt", "dd",
        "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "table", "ul", "ol",
    }
    HEADINGS = {"h1", "h2", "h3"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = ""
        self.images = 0
        self.skip_depth = 0
        self.stack = []
        self.chunks = []          # all visible text
        self.headings = []        # h1-h3 text
        self.paragraphs = []      # <p> text, for the description
        self._buf = None          # capture buffer for the current h*/p

    # -- helpers ----------------------------------------------------------- #
    def _flush(self):
        if self._buf is None:
            return
        tag, parts = self._buf
        text = re.sub(r"\s+", " ", "".join(parts)).strip()
        self._buf = None
        if not text:
            return
        if tag in self.HEADINGS:
            self.headings.append(text)
        else:
            self.paragraphs.append(text)

    # -- HTMLParser hooks --------------------------------------------------- #
    def handle_starttag(self, tag, attrs):
        if tag == "html" and not self.lang:
            self.lang = dict(attrs).get("lang", "") or ""
        if tag == "img":
            self.images += 1
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        self.stack.append(tag)
        if tag in self.HEADINGS or tag == "p":
            self._flush()
            self._buf = (tag, [])
        elif tag in self.BLOCK:
            self.chunks.append(" ")

    def handle_startendtag(self, tag, attrs):
        if tag == "img":
            self.images += 1
        elif tag == "br":
            self.chunks.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag in self.HEADINGS or tag == "p":
            self._flush()
        if tag in self.BLOCK:
            self.chunks.append(" ")
        while self.stack:
            if self.stack.pop() == tag:
                break

    def handle_data(self, data):
        if self.skip_depth:
            return
        self.chunks.append(data)
        if self._buf is not None:
            self._buf[1].append(data)

    # -- results ------------------------------------------------------------ #
    def finish(self):
        self._flush()
        return re.sub(r"\s+", " ", "".join(self.chunks)).strip()


TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
MATH_RE = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]|\$\$(.+?)\$\$", re.S)
META_DESC_RE = re.compile(
    r"""<meta[^>]+name=["']description["'][^>]+content=["'](.*?)["']""", re.I | re.S)
STAMP_RE = re.compile(r"(20\d{6})(?:[_-](\d{6}))?")


def strip_math(text):
    """Reduce MathJax source to its readable words.

    Only touches the inside of \\(…\\), \\[…\\] and $$…$$ — snippets from a
    maths-heavy post are unreadable otherwise, but prose full of snake_case
    paths must survive untouched, so nothing outside a math span is stripped.
    """
    def clean(m):
        inner = next(g for g in m.groups() if g is not None)
        inner = re.sub(r"\\[a-zA-Z]+\*?", " ", inner)   # \text, \frac, \quad …
        inner = re.sub(r"[{}\\^_&$]", " ", inner)
        return " " + re.sub(r"\s+", " ", inner).strip() + " "

    return re.sub(r"\s+", " ", MATH_RE.sub(clean, text)).strip()


def clip(text, limit):
    """Trim to `limit` chars on a word boundary, with an ellipsis if cut."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,;:.–-") + "…"


def prettify(stem):
    words = re.sub(r"[_\-]+", " ", stem).strip()
    return words[:1].upper() + words[1:] if words else stem


def date_of(stem, path):
    m = STAMP_RE.search(stem)
    if m:
        try:
            day = datetime.datetime.strptime(m.group(1), "%Y%m%d")
            if m.group(2):
                t = m.group(2)
                day = day.replace(hour=int(t[0:2]), minute=int(t[2:4]),
                                  second=int(t[4:6]))
            return day
        except ValueError:
            pass
    return datetime.datetime.fromtimestamp(os.path.getmtime(path))


def series_of(stem):
    """Slug family, e.g. mlmatwiss-03-algorithmen_20260729 -> 'mlmatwiss'."""
    base = STAMP_RE.sub("", stem).strip("_-")
    head = re.split(r"[-_]", base, 1)[0].lower()
    if len(head) < 4 or head in SERIES_STOPLIST or head.isdigit():
        return ""
    return head


def read_post(path, root):
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()

    parser = PostParser()
    try:
        parser.feed(raw)
    except Exception as exc:  # a malformed post must not kill the whole build
        print(colored(f"Warning: parse trouble in {path}: {exc}", "yellow"))
    body = strip_math(parser.finish())

    m = TITLE_RE.search(raw)
    title = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else ""
    if not title and parser.headings:
        title = parser.headings[0]

    rel = os.path.relpath(path, root)
    stem = os.path.basename(os.path.dirname(rel)) if os.path.dirname(rel) \
        else os.path.splitext(os.path.basename(rel))[0]
    if not title:
        title = prettify(STAMP_RE.sub("", stem).strip("_-"))

    m = META_DESC_RE.search(raw)
    desc = html.unescape(m.group(1).strip()) if m else ""
    if not desc:
        # first substantial paragraphs, minus one that just repeats the title
        picks = [strip_math(p) for p in parser.paragraphs
                 if len(p) >= 60 and p.lower() != title.lower()]
        desc = " ".join(picks[:2]) if picks else body
    desc = clip(desc, 260)

    # Where the material came from — sidecar first, stamped meta tag as the
    # fallback for a post whose folder was moved. Absent on everything
    # published before provenance existed; those simply carry no source.
    rec = provenance.read(os.path.dirname(path), raw)
    src, src_full = "", ""
    if rec:
        src = rec.get("label", "")
        parts = [rec.get("cwd", "")] + list(rec.get("sources") or [])
        repo = rec.get("repo") or {}
        if repo.get("root") and repo["root"] not in parts:
            parts.insert(0, repo["root"])
        if rec.get("backfill"):
            parts.append("(" + rec["backfill"] + ")")
        src_full = " · ".join(dict.fromkeys(p for p in parts if p))

    when = date_of(stem, path)
    return {
        "h": rel.replace(os.sep, "/"),
        "t": title,
        "d": desc,
        "hd": clip(" · ".join(dict.fromkeys(parser.headings)), 1200),
        "sr": (src + " " + src_full).strip(),
        "src": src,
        "srcp": src_full,
        "x": body,
        "dt": when.strftime("%Y-%m-%d"),
        "ts": int(when.timestamp()),
        "w": len(body.split()),
        "l": (parser.lang or "").split("-")[0].lower(),
        "s": series_of(stem),
        "img": parser.images,
        "kb": round(os.path.getsize(path) / 1024),
    }


def discover(root, out_name):
    """Post paths, folder form preferred, byte-identical duplicates dropped."""
    folder_posts = sorted(glob.glob(os.path.join(root, "*", "index.html")))
    loose_posts = sorted(p for p in glob.glob(os.path.join(root, "*.html"))
                         if os.path.basename(p) != out_name)

    seen, paths, dupes = {}, [], []
    for path in folder_posts + loose_posts:
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        if digest in seen:
            dupes.append((path, seen[digest]))
            continue
        seen[digest] = path
        paths.append(path)
    return paths, dupes


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #

def render(docs, template_path):
    with open(template_path, encoding="utf-8") as f:
        page = f.read()

    series, sources = {}, {}
    for d in docs:
        if d["s"]:
            series[d["s"]] = series.get(d["s"], 0) + 1
        if d["src"]:
            sources[d["src"]] = sources.get(d["src"], 0) + 1
    meta = {
        "built": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "series": sorted(([s, n] for s, n in series.items() if n >= SERIES_MIN),
                         key=lambda x: -x[1]),
        "sources": sorted(([s, n] for s, n in sources.items()), key=lambda x: (-x[1], x[0])),
        "langs": sorted({d["l"] for d in docs if d["l"]}),
        "words": sum(d["w"] for d in docs),
        "tracked": sum(1 for d in docs if d["src"]),
    }

    payload = json.dumps(docs, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # never break out of <script>
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))

    for marker, value in (("/*__DOCS__*/null", payload),
                          ("/*__META__*/null", meta_json)):
        if marker not in page:
            raise SystemExit(f"template is missing the {marker} marker")
        page = page.replace(marker, value, 1)
    return page


def build(root=BLOGPOST_DIR, out=None, template=TEMPLATE, quiet=False):
    out = out or os.path.join(root, INDEX_NAME)
    paths, dupes = discover(root, os.path.basename(out))
    if not paths:
        print(colored(f"No posts found under {root}", "red"))
        return None

    docs = [read_post(p, root) for p in paths]
    docs.sort(key=lambda d: d["ts"], reverse=True)

    # A slug family is only a "series" once several posts share it — otherwise
    # the prefix is just this post's name and makes for a noisy card tag.
    counts = {}
    for d in docs:
        counts[d["s"]] = counts.get(d["s"], 0) + 1
    for d in docs:
        if counts.get(d["s"], 0) < SERIES_MIN:
            d["s"] = ""

    page = render(docs, template)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)

    if not quiet:
        for path, kept in dupes:
            print(colored(f"Skipped duplicate: {os.path.relpath(path, root)} "
                          f"(same bytes as {os.path.relpath(kept, root)})", "yellow"))
        chars = sum(len(d["x"]) for d in docs)
        print(colored(f"Indexed {len(docs)} posts · {chars/1024:.0f} KiB of text · "
                      f"{sum(d['w'] for d in docs):,} words", "green"))
    # Same output contract as main.py / publish.py — callers grep for this line.
    print(colored(f"Saved HTML: {out}", "cyan"))
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Build the searchable index page over blogposts/.")
    parser.add_argument("--out", help=f"output path (default: blogposts/{INDEX_NAME})")
    parser.add_argument("--root", default=BLOGPOST_DIR, help="blogposts directory")
    parser.add_argument("--template", default=TEMPLATE, help="page template")
    parser.add_argument("--open", action="store_true", dest="open_browser",
                        help="open the result in the browser")
    parser.add_argument("--quiet", action="store_true", help="only print the Saved line")
    args = parser.parse_args()

    out = build(args.root, args.out, args.template, args.quiet)
    if not out:
        return 1

    if args.open_browser:
        try:
            webbrowser.register("firefox_custom", None,
                                webbrowser.BackgroundBrowser(BROWSER_PATH))
            browser = webbrowser.get("firefox_custom")
        except Exception:
            browser = webbrowser.get()
        browser.open(f"file://{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
