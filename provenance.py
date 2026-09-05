#!/usr/bin/env python3
"""Record where a blogpost's source material came from.

A published post used to be an orphan: the folder name carries a slug and a
timestamp, the HTML carries the prose, and nothing anywhere says which repo,
file or screenshot it was made from. That makes "list the posts about my mujoco
training" unanswerable except by guessing from the text.

So every publish now writes a `source.json` next to `index.html` and stamps the
same record into the HTML head as a `<meta name="bloggen:provenance">` tag —
the sidecar is easy to read, the meta tag survives the folder being copied or
the file being moved out on its own.

Stdlib-only and import-light on purpose: `publish.py` must keep working without
google.generativeai or a GEMINI_API_KEY, so this module may not pull in
main.py.
"""

import datetime
import html
import json
import os
import re
import socket
import subprocess

RECORD_NAME = "source.json"
META_NAME = "bloggen:provenance"
META_RE = re.compile(
    r"""<meta[^>]+name=["']""" + META_NAME + r"""["'][^>]+content=["'](.*?)["']""",
    re.I | re.S)
HEAD_RE = re.compile(r"</head\s*>", re.I)


def _git(cwd, *args):
    try:
        out = subprocess.run(("git", "-C", cwd) + args, capture_output=True,
                             text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _repo_of(cwd):
    root = _git(cwd, "rev-parse", "--show-toplevel")
    if not root:
        return None
    return {
        "root": root,
        "name": os.path.basename(root),
        "branch": _git(cwd, "rev-parse", "--abbrev-ref", "HEAD"),
        "commit": _git(cwd, "rev-parse", "--short", "HEAD"),
        "remote": _git(cwd, "remote", "get-url", "origin"),
    }


def collect(mode, inputs=None, sources=None, cwd=None):
    """Build the provenance record for a post about to be published.

    mode    — how the HTML was produced ("gemini" or "agent")
    inputs  — files bloggen actually read (images, PDFs, screenshots, …)
    sources — caller-declared origins from --source: a repo path, a file, a URL,
              or a plain topic string when there is no file to point at
    cwd     — working directory of the invocation (defaults to the real one)
    """
    cwd = os.path.abspath(cwd or os.getcwd())
    repo = _repo_of(cwd)

    seen, clean_inputs = set(), []
    for path in inputs or []:
        if not path:
            continue
        full = os.path.abspath(path)
        if full not in seen:
            seen.add(full)
            clean_inputs.append(full)

    declared = [s for s in (sources or []) if s]

    # The label is what the index groups and filters on, so it wants to name a
    # *project*, not a file: the repo wins over a declared "…/status.html",
    # which would make a useless chip. The specific origin is not lost — it
    # stays in sources[] and stays searchable.
    if repo:
        label = repo["name"]
    elif declared:
        first = declared[0]
        label = os.path.basename(first.rstrip("/")) if os.path.sep in first else first
    else:
        label = os.path.basename(cwd) or cwd

    return {
        "bloggen": 1,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "mode": mode,
        "label": label,
        "cwd": cwd,
        "repo": repo,
        "sources": declared,
        "inputs": clean_inputs,
    }


def write(post_dir, record):
    """Drop the sidecar next to index.html. Returns its path."""
    path = os.path.join(post_dir, RECORD_NAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def stamp(html_text, record):
    """Inject the record into the HTML head; unchanged if there is no head."""
    if META_RE.search(html_text):
        html_text = META_RE.sub("", html_text, count=1)
    if not HEAD_RE.search(html_text):
        return html_text
    payload = html.escape(json.dumps(record, ensure_ascii=False,
                                     separators=(",", ":")), quote=True)
    tag = '<meta name="' + META_NAME + '" content="' + payload + '">\n'
    return HEAD_RE.sub(tag + "</head>", html_text, count=1)


def read(post_dir=None, html_text=None):
    """Recover a record from the sidecar, else from the stamped meta tag."""
    if post_dir:
        path = os.path.join(post_dir, RECORD_NAME)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                pass
    if html_text:
        m = META_RE.search(html_text)
        if m:
            try:
                return json.loads(html.unescape(m.group(1)))
            except ValueError:
                pass
    return None


def describe(record):
    """One-line summary for the terminal."""
    if not record:
        return ""
    bits = [record["label"]]
    if record.get("repo") and record["repo"].get("commit"):
        bits.append(record["repo"]["branch"] + "@" + record["repo"]["commit"])
    n = len(record.get("inputs") or [])
    if n:
        bits.append(str(n) + (" input" if n == 1 else " inputs"))
    return " · ".join(bits)
