#!/usr/bin/env python3
"""Publish an agent-authored HTML blogpost into the bloggen blogposts/ tree.

This is the *publishing half* of bloggen, split out so a caller that has already
written the HTML itself (an agent authoring the post from its own context) can
reuse the folder layout, image co-location, and browser-open behaviour without
going through Gemini generation.

Deliberately standalone: it does NOT import main.py, which pulls in
google.generativeai, termios/tty terminal machinery and a GEMINI_API_KEY
requirement at module scope. The only things duplicated from main.py are the
output-dir and browser constants below — keep them in sync.

Usage:
    publish.py --html post.html [--image-files a.png b.png] [--name my-post]
               [--no-open]

Contract for the HTML: reference images by **basename only**
(`<img src="fig1.png">`), and pass those files via --image-files. They are
copied next to index.html, so bare relative refs resolve. Any <img src> that
looks like a path or points at a file not supplied is reported as a warning.
"""

import argparse
import datetime
import os
import re
import shutil
import sys
import webbrowser

# --- kept in sync with main.py ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLOGPOST_DIR = os.path.join(SCRIPT_DIR, "blogposts")
BROWSER_PATH = os.getenv("BROWSER_PATH", "/usr/bin/firefox")

try:
    from termcolor import colored
except ImportError:  # keep the tool usable without termcolor
    def colored(text, *_args, **_kwargs):
        return text


def slugify(text, fallback="blogpost"):
    safe = re.sub(r"[^\w\-]", "_", text or "").strip("_")
    safe = re.sub(r"_+", "_", safe)
    return safe[:60] or fallback


def title_from_html(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def check_image_refs(html, provided_basenames):
    """Warn about <img src> refs that won't resolve in the post folder."""
    warnings = []
    refs = re.findall(r"<img[^>]+src\s*=\s*[\"']([^\"']+)[\"']", html, re.IGNORECASE)
    for ref in refs:
        if ref.startswith(("http://", "https://", "data:")):
            continue
        if "/" in ref:
            warnings.append(
                f"<img src=\"{ref}\"> is a path — use the basename only "
                f"(\"{os.path.basename(ref)}\") and pass the file via --image-files"
            )
        elif ref not in provided_basenames:
            warnings.append(
                f"<img src=\"{ref}\"> has no matching file in --image-files"
            )
    for name in provided_basenames:
        if name not in refs:
            warnings.append(f"--image-files carries {name}, but no <img> references it")
    return warnings


def publish(html_path, image_files, name=None, open_browser=True):
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    if "<html" not in html.lower():
        print(colored("Warning: input does not look like a full HTML document.", "yellow"))

    stem = name or title_from_html(html) or "blogpost"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    post_dir = os.path.join(BLOGPOST_DIR, f"{slugify(stem)}_{timestamp}")
    os.makedirs(post_dir, exist_ok=True)

    basenames = []
    for src in image_files or []:
        if not os.path.isfile(src):
            print(colored(f"Error: image not found: {src}", "red"))
            return None
        dest = os.path.join(post_dir, os.path.basename(src))
        shutil.copy(src, dest)
        basenames.append(os.path.basename(src))
        print(colored(f"Saved image: {dest}", "cyan"))

    for warning in check_image_refs(html, basenames):
        print(colored(f"Warning: {warning}", "yellow"))

    out_html = os.path.join(post_dir, "index.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    # Same output contract as main.py — callers grep for this line.
    print(colored(f"Saved HTML: {out_html}", "cyan"))

    if open_browser:
        print(colored("\nOpening in browser...", "blue"))
        try:
            webbrowser.register(
                "firefox_custom", None, webbrowser.BackgroundBrowser(BROWSER_PATH)
            )
            browser = webbrowser.get("firefox_custom")
        except Exception:
            browser = webbrowser.get()
        browser.open(f"file://{out_html}")

    return out_html


def main():
    parser = argparse.ArgumentParser(
        description="Publish an agent-authored HTML blogpost (no Gemini involved)."
    )
    parser.add_argument("--html", required=True, help="Path to the authored HTML file")
    parser.add_argument("--image-files", nargs="*", default=[],
                        help="Images the HTML references by basename")
    parser.add_argument("--name", help="Folder-name stem (default: the <title>)")
    parser.add_argument("--no-open", action="store_true", help="Do not launch the browser")
    args = parser.parse_args()

    if not os.path.isfile(args.html):
        print(colored(f"Error: no such file: {args.html}", "red"))
        return 1

    return 0 if publish(args.html, args.image_files, args.name, not args.no_open) else 1


if __name__ == "__main__":
    sys.exit(main())
