import os
import subprocess
import sys
import re
import argparse
import json
from pathlib import Path

# ================= ADVERTISEMENT =================
if "--advertise" in sys.argv:
    metadata = [{
        "name": "BlogGen",
        "capability": "summarize",
        "domain": "html",
        "category": "research",
        "desktop_file": "bloggen.desktop",
        "icon": "document-edit",
        "desc": "Generate a styled, self-contained HTML blogpost from images, PDFs, or text",
        "terminal": False,
        "args": [],
        "tags": ["CLI", "Icon"],
        "skill_name": "bloggen",  # surfaces a Skill checkbox in the installer GUI
    }]
    print(json.dumps(metadata))
    sys.exit(0)

# Add root directory to path for shared module imports
# Two levels up: tool_dir -> category_dir -> root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ================= CLAUDE SKILL (single source of truth) =================
# Edit SKILL_MD_TEMPLATE here, then run `python main.py --install-skill`.
# Never hand-edit the installed file — --install-skill overwrites it.
# The template carries {tool_dir} / {python} / {env_file} placeholders that
# render_skill_md() fills in from THIS checkout at install time, so the written
# SKILL.md names the paths of the machine it was installed on and no author's
# layout is baked into the source.
# Legacy skill dir names this tool has shipped under; pruned on (re)install so
# hosts that synced an older name don't keep a stale ~/.claude/skills entry.
_LEGACY_SKILL_NAMES = ["screenshot-blogpost"]
SKILL_DIR = Path.home() / ".claude" / "skills" / "bloggen"
SKILL_FILE = SKILL_DIR / "SKILL.md"
TOOL_DIR = Path(__file__).resolve().parent

SKILL_MD_TEMPLATE = '''---
name: bloggen
description: Turn a screenshot, image(s), PDF, pasted text, or the current conversation into a self-contained, styled HTML blogpost saved to disk and opened in the browser. You may author the HTML yourself (default) or delegate writing to Gemini. Use when the user wants content written up as a shareable HTML article — "make a blogpost from this screenshot/image/PDF", "turn this into an HTML write-up", "write up what's in this screenshot", "turn our conversation/this discussion into a blogpost", "Blogpost aus diesem Screenshot/Bild/PDF", "mach aus unserem Gespräch einen Artikel". NOT for plain OCR / text or LaTeX extraction (use transcribe-image) and NOT for the daily digest (use digest).
---

# BlogGen — image/PDF/text/conversation -> styled HTML blogpost

Produces a self-contained HTML5 blogpost (inline CSS, responsive layout,
optional MathJax) in its own folder under the tool's `blogposts/` directory —
an `index.html` plus every image it references — and opens it in Firefox.

The writing can be done two ways. **Pick the mode before you run anything.**

## Mode B — you author it (DEFAULT — prefer this)

**Do both phases yourself:** analyse the source, then write the HTML, then hand
it to `publish.py` for the folder/image/browser mechanics. No Gemini involved.

This is the default because you almost always already hold the content, and
delegating then means paying a second model to paraphrase your own summary —
which adds wording drift without adding information. Choose Mode B when:

- **any claim must be traceable** — repo state, measured numbers, quoted
  results, anything a reviewer/professor/colleague will check;
- the source **is the conversation** (Gemini would only ever see your lossy
  summary of it, never the real thread);
- you already read the files/images being written about;
- a specific structure, house style, or language is required;
- the user asked for *your* writing, or wants to iterate on the text with you.

```bash
PUB={tool_dir}/publish.py
PY={python}

# 1. Start from the house template so styling stays consistent across modes:
#    {tool_dir}/assets/template.html
#    Read it, fill TITLE / standfirst / <article> body, drop the MathJax
#    <script> pair if there is no maths. Write the result anywhere, e.g.
#    the scratchpad.
# 2. Reference images by BASENAME ONLY: <img src="fig1.png">
# 2b. Write in the language of the source: a German screenshot/PDF/conversation
#     gets a German post. Set <html lang="de"> to match - the index reads it.
# 3. Publish (creates blogposts/<slug>_<timestamp>/, copies images, opens Firefox):
"$PY" "$PUB" --html /path/post.html --image-files /abs/fig1.png /abs/fig2.png
```

`publish.py` flags: `--name <slug>` (default: the `<title>`), `--no-open`,
`--source <origin ...>`.
It warns if an `<img src>` is a path rather than a basename, references a file
you did not pass, or if a supplied image is never referenced — fix those, they
mean a broken image in the published post.

## Always record where the material came from

Every post gets a `source.json` sidecar (and a matching `<meta>` tag) naming
the working directory, the git repo + commit, and the inputs. That is what
makes "list the posts about my mujoco training" answerable later, so:

- **Run publish.py from the directory the post is about** — the repo the work
  happened in, not the scratchpad. The cwd is captured automatically.
- Add `--source` when the origin is more specific than the cwd or is not a
  file at all: `--source .state/status.html`, `--source https://…`,
  `--source "conversation: sim-to-sim transfer gap"`. Repeatable.
- Both apply to Mode A too (`main.py --source …`).

## Mode A — delegate to Gemini

Two-phase Gemini run: it *analyzes* the supplied content (text + images), then
*generates* the whole post — prose, CSS, layout — expanding on what it found.
Costs no agent tokens and needs no reading on your part.

Use when the source is an **artifact you have not ingested** (a long PDF, a
screenshot you are not otherwise reading), when per-claim fidelity does not
matter much, or when the user explicitly wants the tool's own voice/flair.

**Do not use Mode A to write up work you already know** — that is the case
Mode B exists for.

### Invocation — use absolute paths, NOT the alias/desktop entry

Run the tool's headless `--analyze-only` content mode directly. Re-define these
in **every** Bash call (shell state does not persist between calls). The
`BLOGGEN_ENV` export points the tool at the `.env` holding `GEMINI_API_KEY`
(plus any shared model lists) — the tool parses it with python-dotenv, which
handles the multi-line model lists that a shell `source` chokes on. Set it only
to override the default; without it the tool reads the `.env` beside `main.py`:

```bash
PY={python}
SB={tool_dir}/main.py
export BLOGGEN_ENV={env_file}
```

### Mode A commands

```bash
# From one or more images
"$PY" "$SB" --analyze-only --image-files /path/a.png /path/b.jpg

# From a PDF (extracts its text AND embedded images)
"$PY" "$SB" --analyze-only --text-files /path/paper.pdf

# From a single screenshot/image (screenshot-specific prompt + hero image)
"$PY" "$SB" --analyze-only --screenshot-path /path/shot.png

# From literal/pasted text, or from the current conversation — write it to a
# file first (summarise the discussion into it), then pass it
printf '%s' "the text to write up" > /tmp/sb_text.txt
"$PY" "$SB" --analyze-only --raw-text-file /tmp/sb_text.txt

# Mix any of the above in one post
"$PY" "$SB" --analyze-only --text-files notes.pdf --image-files fig1.png --raw-text-file /tmp/sb_text.txt
```

## Mode C — hybrid (rare)

Run Mode A, then **read the generated `index.html` and correct it** against your
own knowledge of the source before showing the user. Worth it only when you want
Gemini's design work but need your accuracy. Say plainly in your reply that you
patched it.

## Output (both modes)
- Saves a per-post folder `blogposts/<name>/` containing `index.html`
  plus its images, under `.../AutomatedAlchemy/bloggen/blogposts/`, and
  prints the path as `Saved HTML: <path>` — read that line back to the user.
- Auto-opens the result in Firefox.
- Non-interactive runs (Claude's Bash tool) skip the end-of-run countdown and
  return promptly.

## Reporting to the user
State which mode you used. If Gemini wrote the prose (Mode A), **say so** — the
user needs to know the wording is not yours before forwarding it to anyone.

## Notes
- Mode B needs no API key. Mode A needs `GEMINI_API_KEY` in
  `{env_file}`, or in any `.env` named by `BLOGGEN_ENV`.
- Prefers `gemini-3.6-flash`, then falls back through the shared `.env` model lists.
- `--text-files` accepts PDFs (text + images extracted) and plain-text files.
- `--image-files` accepts ordinary image files; up to 5 images per PDF are pulled in.
- This tool *writes about* the content (generation). For straight OCR / LaTeX
  extraction of a page, use the `transcribe-image` skill instead.
'''


def _tool_python() -> str:
    """The interpreter the skill's example commands should use.

    Prefer a venv the tool owns (that is where its dependencies are installed by
    the cli-tools-kit installer), otherwise the interpreter running this script.
    """
    for candidate in (TOOL_DIR / ".venv" / "bin" / "python3",
                      TOOL_DIR / ".venv" / "bin" / "python",
                      TOOL_DIR / ".venv" / "Scripts" / "python.exe"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def render_skill_md() -> str:
    """Fill the SKILL.md template with this checkout's paths."""
    return SKILL_MD_TEMPLATE.format(
        tool_dir=TOOL_DIR,
        python=_tool_python(),
        env_file=TOOL_DIR / ".env",
    )


def _prune_legacy_skill_dirs() -> None:
    """Drop skill dirs from previous names of this tool (e.g. screenshot-blogpost)."""
    skills_root = SKILL_DIR.parent
    for legacy in _LEGACY_SKILL_NAMES:
        legacy_dir = skills_root / legacy
        if legacy_dir == SKILL_DIR or not legacy_dir.exists():
            continue
        legacy_file = legacy_dir / "SKILL.md"
        try:
            if legacy_file.exists():
                legacy_file.unlink()
            legacy_dir.rmdir()  # only if now empty
            print(f"  Pruned legacy skill dir: {legacy_dir}")
        except OSError:
            pass


def _install_skill() -> None:
    """Write (or refresh) ~/.claude/skills/bloggen/SKILL.md from the inline source."""
    _prune_legacy_skill_dirs()
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    content = render_skill_md()
    pre_existed = SKILL_FILE.exists()
    if pre_existed and SKILL_FILE.read_text(encoding="utf-8") == content:
        print(f"  - Skill already up-to-date: {SKILL_FILE}")
        return
    SKILL_FILE.write_text(content, encoding="utf-8")
    verb = "Refreshed" if pre_existed else "Installed"
    print(f"  Skill {verb}: {SKILL_FILE}")
    print("  Claude Code picks this up live - no restart needed.")


def _uninstall_skill() -> None:
    """Remove ~/.claude/skills/bloggen/SKILL.md (and the empty dir)."""
    _prune_legacy_skill_dirs()
    if SKILL_FILE.exists():
        SKILL_FILE.unlink()
        print(f"  Removed {SKILL_FILE}")
    else:
        print(f"  No skill file at {SKILL_FILE}")
    try:
        SKILL_DIR.rmdir()  # only if empty
    except OSError:
        pass


if "--install-skill" in sys.argv:
    _install_skill()
    sys.exit(0)
if "--uninstall-skill" in sys.argv:
    _uninstall_skill()
    sys.exit(0)

# ================= INSTALL / REMOVE (before heavy imports) =================
# Canonical import is the cli_tools_kit pip package; fall back to the in-tree
# shim for environments without it (subtree exports, etc.).
if "--install" in sys.argv or "--remove" in sys.argv:
    try:
        from cli_tools_kit import ToolInstaller, ToolMetadata
    except ImportError:
        try:
            from _shared.tool_installer import ToolInstaller, ToolMetadata
        except ImportError:
            print(
                "--install/--remove need the cli-tools-kit package "
                "(pip install cli-tools-kit). Blogpost generation itself works "
                "without it via the CLI flags — see the README."
            )
            sys.exit(1)

    _installer = ToolInstaller(
        script_path=__file__,
        metadata=ToolMetadata(
            name="BlogGen",
            desktop_file="bloggen.desktop",
            icon="document-edit",
            desc="Generate a styled, self-contained HTML blogpost from images, PDFs, or text",
            categories="Utility;Office;",
        ),
    )
    if "--install" in sys.argv:
        _installer.install()
        _install_skill()  # best-effort so direct CLI use is one-shot
    else:
        _installer.remove()
        _uninstall_skill()
    sys.exit(0)

import shutil
import webbrowser
import select
import termios
import tty
import traceback
import tempfile
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from PIL import Image
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from termcolor import colored

# Optional PDF support - graceful fallback if not installed
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False


# ================= CONFIGURATION =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Load a .env without baking in any one checkout layout: an explicit override
# first, then the tool's own directory, then a walk up the tree (so a .env at a
# parent/repo root is still found). If none exist we fall back to the process
# environment (e.g. GEMINI_API_KEY exported by the shell), so the tool stays
# usable both standalone and inside a larger workspace.
_env_override = os.environ.get("BLOGGEN_ENV") or os.environ.get("SCREENSHOT_BLOGPOST_ENV")
_local_env = os.path.join(SCRIPT_DIR, ".env")
_env_path = _env_override or (_local_env if os.path.exists(_local_env) else find_dotenv(usecwd=False))
if _env_path:
    load_dotenv(_env_path)

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model this tool prefers, kept ahead of the shared .env lists so the blogpost
# generator uses it first; the env-configured models remain as fallbacks (and
# the generation loop already skips a MODEL NOT FOUND id gracefully).
# Overridable per run with BLOGGEN_MODEL=<model id>.
PREFERRED_MODEL = os.getenv("BLOGGEN_MODEL", "gemini-3.6-flash")

def get_candidate_models():
    """Unique, ordered model list: PREFERRED_MODEL first, then any models from the
    shared .env vars, then a hardcoded fallback when no env vars are set."""
    models = [PREFERRED_MODEL]
    # Priority order for fallback: specific var -> list var -> strong var
    for var in ["COMPETENT_GEMINI_MODELS", "STRONG_GEMINI_MODELS"]:
        val = os.getenv(var)
        if val:
            for m in val.split(","):
                m = m.strip()
                if m and m not in models:
                    models.append(m)
    if models == [PREFERRED_MODEL]:
        models += ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"]
    return models

GEMINI_CANDIDATE_MODELS = get_candidate_models()
BROWSER_PATH = os.getenv("BROWSER_PATH", "/usr/bin/firefox")
# Per-invocation tempdir avoids the symlink-race on a fixed /tmp/<name>.png path
# (a local attacker on a shared host could pre-symlink it at any writable target).
import tempfile as _tempfile
TEMP_FILENAME = os.path.join(
    _tempfile.mkdtemp(prefix="bloggen_"), "screenshot.png"
)
BLOGPOST_DIR = os.path.join(SCRIPT_DIR, "blogposts")

# Folder-per-post layout: every run gets its OWN subdirectory under blogposts/,
# holding index.html plus all images it references. This keeps the HTML's bare
# <img src="foo.png"> relative refs working while isolating each post. Follow-up
# revisions within one session re-reference the original post's images by name,
# so all revisions of a session share this single directory (established at the
# first save, reused thereafter). See _session_post_dir().
_SESSION_POST_DIR = None

# Provenance for this invocation — where the material came from. Filled in by
# main() from the CLI args, read by both save paths. See provenance.py.
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import provenance  # noqa: E402  — sibling module, needs SCRIPT_DIR on sys.path

_SOURCE_INPUTS = []      # files this run actually read
_SOURCE_DECLARED = []    # --source values, if the caller named an origin


def _record_provenance(post_dir, html_content):
    """Write the sidecar, stamp the HTML, report it. Returns the new HTML."""
    record = provenance.collect("gemini", inputs=_SOURCE_INPUTS,
                                sources=_SOURCE_DECLARED)
    provenance.write(post_dir, record)
    print(colored(f"Source: {provenance.describe(record)}", "cyan"))
    return provenance.stamp(html_content, record)


def _session_post_dir(base_name):
    """Return this session's post folder under blogposts/, creating it once.

    The first save in a session wins the folder name; follow-up saves reuse the
    same folder so their images stay co-located. `base_name` is the descriptive
    stem (no extension) the old flat filename would have used, e.g.
    "blogpost_20260714_153904" or "blogpost_Uebung_1_pdf_20260120_112316".
    """
    global _SESSION_POST_DIR
    if _SESSION_POST_DIR is None:
        safe = re.sub(r'[^\w\-]', '_', base_name).strip('_') or "blogpost"
        _SESSION_POST_DIR = os.path.join(BLOGPOST_DIR, safe)
        os.makedirs(_SESSION_POST_DIR, exist_ok=True)
    return _SESSION_POST_DIR


# ================= UTILS & INSTALLATION =================

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate HTML blogpost from screenshot using AI")
    parser.add_argument("--install", action="store_true", help="Install desktop shortcut")
    parser.add_argument("--remove", action="store_true", help="Remove desktop shortcut")
    parser.add_argument("--analyze-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--screenshot-path", type=str, help=argparse.SUPPRESS)  # Parent passes its per-invocation temp screenshot path to the child
    parser.add_argument("--text-files", type=str, nargs='*', help=argparse.SUPPRESS)  # Paths to text/PDF files
    parser.add_argument("--image-files", type=str, nargs='*', help=argparse.SUPPRESS)  # Paths to image files
    parser.add_argument("--raw-text-file", type=str, help=argparse.SUPPRESS)  # Path to temp file with pasted text
    parser.add_argument("--content-dir", type=str, help=argparse.SUPPRESS)  # Directory with extracted PDF images
    parser.add_argument("--source", type=str, nargs='*', default=[], metavar="ORIGIN",
                        help="Where the material came from: a path, a repo, a URL, or a "
                             "topic. The working directory is recorded either way.")
    return parser.parse_args()


def launch_terminal_process():
    python_exec = sys.executable
    script_path = os.path.abspath(__file__)
    # Pass the parent's per-invocation temp path explicitly: the child is a fresh
    # Python process and would otherwise call mkdtemp() again, landing on a
    # different dir and failing to find the screenshot the parent just saved.
    cmd = ["konsole", "-e", python_exec, script_path,
           "--analyze-only", "--screenshot-path", TEMP_FILENAME]
    subprocess.Popen(cmd)

def auto_close_timer(seconds=10):
    """Counts down if success. If ESC pressed, stays open."""
    # Non-interactive (agent/headless) stdin has no TTY to read keys from and
    # termios.tcgetattr would raise — nothing to wait on, so return promptly.
    if not sys.stdin.isatty():
        return
    print(colored(f"\n[SUCCESS] Closing in {seconds} seconds. Press ESC to keep open.", "white"))

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        for i in range(seconds, 0, -1):
            sys.stdout.write(f"\rClosing in {i}s...  ")
            sys.stdout.flush()
            if select.select([sys.stdin], [], [], 1)[0]:
                key = sys.stdin.read(1)
                if key == '\x1b':  # ESC
                    sys.stdout.write("\nAuto-close CANCELLED. Window will stay open.\n")
                    input("\nPress Enter to close manually...")
                    return
    except Exception:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def manual_hold_on_crash():
    print(colored("\n-------------------------------------------", "red", attrs=["bold"]))
    print(colored("    PROCESS FAILED. WINDOW HELD OPEN.      ", "red", attrs=["bold"]))
    print(colored("-------------------------------------------", "red", attrs=["bold"]))
    try:
        input(colored("Press Enter to close terminal...", "white", attrs=["bold"]))
    except:
        pass

def get_cursor_position():
    if not sys.stdin.isatty():
        return 1, 1
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\033[6n")
        sys.stdout.flush()
        # Read at the raw fd level (os.read) rather than through the buffered
        # sys.stdin text stream. Mixing the two loses bytes: sys.stdin.read()
        # may slurp trailing bytes into Python's internal buffer where a later
        # os.read()/select() can't see them.
        resp = b""
        while True:
            resp += os.read(fd, 1)
            if resp.endswith(b'R'):
                break
        m = re.match(rb'.*?\[(\d+);(\d+)R', resp)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    return 1, 1

def read_input_event():
    # Read at the raw fd level (os.read) rather than through the buffered
    # sys.stdin text stream. sys.stdin.read(1) can slurp a whole chunk into
    # Python's internal buffer and hand back one char; a subsequent select()
    # on the fd then reports "nothing available" (the bytes are hidden in the
    # buffer, not the OS), so a multi-byte escape sequence fragments and stray
    # coordinate digits leak out as phantom "1/2/3" hotkey presses. os.read +
    # fd-level select keeps select() honest.
    fd = sys.stdin.fileno()
    ch = os.read(fd, 1)
    if ch != b'\x1b':
        return ch.decode('utf-8', 'ignore')
    seq = ch
    # We saw ESC — assemble the full escape sequence. Under high-frequency mouse
    # motion reporting (mode 1003) the bytes of a sequence can dribble in across
    # scheduler gaps, so once we know it's a CSI/SS3 sequence we keep reading
    # until its terminating byte instead of bailing on a short per-byte timeout.
    if not select.select([fd], [], [], 0.2)[0]:
        return '\x1b'  # lone ESC (Escape key)
    seq += os.read(fd, 1)
    if seq[-1:] == b'[':
        # CSI sequence: parameter/intermediate bytes (0x20-0x3F) then a final
        # byte in 0x40-0x7E ('@'..'~'). Covers arrows (A/B/C/D), SGR mouse
        # (M/m) and cursor-position reports (R).
        while True:
            if not select.select([fd], [], [], 0.5)[0]:
                break
            c = os.read(fd, 1)
            seq += c
            if 0x40 <= c[0] <= 0x7e:
                break
    elif seq[-1:] == b'O':
        # SS3 sequence (application cursor keys: \x1bOA etc.) — one more byte.
        if select.select([fd], [], [], 0.5)[0]:
            seq += os.read(fd, 1)
    return seq.decode('utf-8', 'ignore')

def parse_sgr_mouse(seq):
    # SGR mouse report format is "\x1b[<btn;col;row" then a single terminator
    # 'M' (press/motion) or 'm' (release) — no semicolon before the terminator.
    m = re.match(r'^\x1b\[<(\d+);(\d+);(\d+)([Mm])$', seq)
    if m:
        pb = int(m.group(1))
        px = int(m.group(2))
        py = int(m.group(3))
        is_press = m.group(4) == 'M'
        return pb, px, py, is_press
    return None

def flush_stdin():
    if not sys.stdin.isatty():
        return
    try:
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except:
        pass

def draw_menu(R_start, active_index):
    sys.stdout.write(f"\033[{R_start};1H")
    border_color = "cyan"
    title_color = "white"
    b1_text = "     1. Enter Prompt     "
    b2_text = "   2. Take Screenshot    "
    b3_text = "         3. Exit         "
    if active_index == 0:
        b1_disp = colored(b1_text, "white", "on_blue", attrs=["bold"])
    else:
        b1_disp = colored(b1_text, "dark_grey")
    if active_index == 1:
        b2_disp = colored(b2_text, "white", "on_blue", attrs=["bold"])
    else:
        b2_disp = colored(b2_text, "dark_grey")
    if active_index == 2:
        b3_disp = colored(b3_text, "white", "on_blue", attrs=["bold"])
    else:
        b3_disp = colored(b3_text, "dark_grey")
    # Each button cell is 25 columns wide, so every horizontal rule must split
    # its 77 inner columns as 25/25/25 (with two connectors) for the ┬/┴ joints
    # to line up under the │ dividers in the button row. (They were 26/26/23,
    # which drifted every connector one column to the right.)
    seg = "─" * 25
    top_row = "┌" + "─" * 77 + "┐"
    mid_row = "├" + seg + "┬" + seg + "┬" + seg + "┤"
    bot_row = "└" + seg + "┴" + seg + "┴" + seg + "┘"
    sys.stdout.write(colored(top_row + "\n", border_color))
    sys.stdout.write(colored("│", border_color) + colored("CHOOSE AN ACTION".center(77), title_color, attrs=["bold"]) + colored("│\n", border_color))
    sys.stdout.write(colored(mid_row + "\n", border_color))
    sys.stdout.write(colored("│", border_color) + b1_disp + colored("│", border_color) + b2_disp + colored("│", border_color) + b3_disp + colored("│\n", border_color))
    sys.stdout.write(colored(bot_row + "\n", border_color))
    sys.stdout.flush()

def save_and_open_followup_blogpost(html_content, combined_name):
    # A follow-up is a revised version of the current session's post: it lives in
    # the SAME folder (already created by the first save, so this reuses it) and
    # overwrites index.html. Its images were copied in by the original save.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = re.sub(r'[^\w\-]', '_', combined_name)[:30]
    post_dir = _session_post_dir(f"blogpost_{base_name}_{timestamp}")
    html_path = os.path.join(post_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(colored(f"Saved follow-up HTML: {html_path}", "cyan"))
    print(colored(f"\nOpening in browser...", "blue"))
    try:
        webbrowser.register('firefox_custom', None, webbrowser.BackgroundBrowser(BROWSER_PATH))
        browser = webbrowser.get('firefox_custom')
    except:
        browser = webbrowser.get()
    browser.open(f"file://{html_path}")
    return html_path

def generate_followup_blogpost(chat, prompt_message):
    history = list(chat.history)
    for model_idx, model_name in enumerate(GEMINI_CANDIDATE_MODELS):
        try:
            print(colored(f"\n[TRYING MODEL: {model_name}] for follow-up", "white", attrs=["bold"]))
            model = genai.GenerativeModel(model_name)
            new_chat = model.start_chat(history=history)
            print(colored("\n--- Follow-up HTML Generation ---", "green", attrs=["bold"]))
            response = new_chat.send_message(
                prompt_message,
                stream=True,
                safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
            )
            html_response = stream_response(response, "green")
            print(colored("\n===============================================", "green", attrs=["bold"]))
            if not html_response.strip():
                raise ValueError("Empty HTML response")
            html_content = extract_html(html_response)
            if html_content:
                return html_content, new_chat
            else:
                print(colored("\nWarning: Could not extract HTML. Trying next model...", "yellow"))
                continue
        except Exception as e:
            error_msg = str(e)
            if is_transient_error(error_msg) and model_idx < len(GEMINI_CANDIDATE_MODELS) - 1:
                print(colored(f"\n[!] TRANSIENT ERROR: {error_msg[:60]}... Trying next model...", "yellow"))
                continue
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(colored(f"\n[!] MODEL NOT FOUND: {model_name}. Skipping...", "yellow"))
                continue
            elif model_idx < len(GEMINI_CANDIDATE_MODELS) - 1:
                print(colored(f"\n[!] ERROR: {error_msg[:60]}... Trying next model...", "yellow"))
                continue
            else:
                raise
    raise RuntimeError("All models failed during follow-up HTML generation.")

def handle_action(action_idx, chat, last_image_filename, combined_name, R_start, old_settings):
    sys.stdout.write("\033[?1003l\033[?1006l\033[?25h\n")
    sys.stdout.flush()
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    flush_stdin()
    if action_idx == 2:
        print(colored("Exiting. Goodbye!", "cyan"))
        return True, chat
    if action_idx == 0:
        print(colored("\n--- ENTER PROMPT ---", "cyan", attrs=["bold"]))
        try:
            user_prompt = input("Enter your prompt: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(colored("\nPrompt cancelled.", "yellow"))
            return False, chat
        if not user_prompt:
            print(colored("Empty prompt. Continuing...", "yellow"))
            return False, chat
        prompt_message = f"""USER REQUEST:
{user_prompt}

YOUR TASK:
1. Plan your approach (think out loud): What changes/additions/updates are needed based on the user request?
2. Generate another complete, updated HTML blogpost from scratch. Do not just output fragments - write the entire self-contained HTML5 document.
3. Include the original/existing images (if any) using their filenames.
4. Output the complete HTML wrapped in ```html ... ```."""
        try:
            html_content, new_chat = generate_followup_blogpost(chat, prompt_message)
            if html_content:
                save_and_open_followup_blogpost(html_content, combined_name)
                chat = new_chat
        except Exception as e:
            print(colored(f"\nError generating blogpost: {e}", "red"))
            traceback.print_exc()
    elif action_idx == 1:
        print(colored("\n--- TAKE SCREENSHOT ---", "cyan", attrs=["bold"]))
        print(colored("Please select a region for the new screenshot...", "yellow"))
        screenshot_taken = take_screenshot()
        if not screenshot_taken:
            print(colored("Screenshot cancelled or failed.", "yellow"))
            return False, chat
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_image_filename = f"screenshot_{timestamp}.png"
        # Land the new screenshot in this session's post folder so the follow-up
        # HTML's <img src="screenshot_...png"> resolves alongside index.html.
        new_img_path = os.path.join(_session_post_dir(combined_name), new_image_filename)
        try:
            shutil.copy(TEMP_FILENAME, new_img_path)
            print(colored(f"Saved new image: {new_img_path}", "cyan"))
        except Exception as e:
            print(colored(f"Failed to copy screenshot: {e}", "red"))
            return False, chat
        finally:
            cleanup(TEMP_FILENAME)
        prompt_text = f"""Here is a new screenshot.

YOUR TASK:
1. Observe the new image and analyze its content.
2. Plan your approach (think out loud): How will you integrate this new screenshot/information into the blogpost?
3. Generate another complete, updated HTML blogpost from scratch. Make sure to present both the original content and this new screenshot/information.
4. Use the new screenshot filename: {new_image_filename} (include it as <img src="{new_image_filename}">).
5. Output the complete HTML wrapped in ```html ... ```."""
        try:
            img = Image.open(new_img_path)
            prompt_message = [prompt_text, img]
            html_content, new_chat = generate_followup_blogpost(chat, prompt_message)
            if html_content:
                save_and_open_followup_blogpost(html_content, combined_name)
                chat = new_chat
        except Exception as e:
            print(colored(f"\nError generating blogpost: {e}", "red"))
            traceback.print_exc()
    return False, chat

def run_interactive_loop(chat, last_image_filename, combined_name):
    if not sys.stdin.isatty():
        return
    print(colored("\nTerminal kept open. Keyboard & stylus control enabled.", "green", attrs=["bold"]))
    R_start, _ = get_cursor_position()
    print("\n\n\n\n")
    R_start, _ = get_cursor_position()
    R_start = max(1, R_start - 5)
    active_index = 0
    draw_menu(R_start, active_index)
    sys.stdout.write("\033[?1003h\033[?1006h\033[?25l")
    sys.stdout.flush()
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                event = read_input_event()
                if not event:
                    continue
                if event == '\r' or event == '\n':
                    action_idx = active_index
                    break_loop, chat = handle_action(action_idx, chat, last_image_filename, combined_name, R_start, old_settings)
                    if break_loop:
                        break
                    R_start, _ = get_cursor_position()
                    print("\n\n\n\n")
                    R_start, _ = get_cursor_position()
                    R_start = max(1, R_start - 5)
                    # handle_action() restored the terminal to cooked/echo mode
                    # (old_settings); re-enter cbreak before re-enabling mouse
                    # reporting, else the incoming mouse escape codes get echoed
                    # to the screen as visible garbage.
                    tty.setcbreak(sys.stdin.fileno())
                    sys.stdout.write("\033[?1003h\033[?1006h\033[?25l")
                    sys.stdout.flush()
                    draw_menu(R_start, active_index)
                # Arrow keys: normal mode (\x1b[A/B/C/D) AND
                # application cursor mode (\x1bOA/B/C/D) — Konsole switches
                # to application mode when SGR mouse reporting is active.
                elif event in ('\x1b[A', '\x1b[D', '\x1bOA', '\x1bOD'):
                    active_index = (active_index - 1) % 3
                    draw_menu(R_start, active_index)
                elif event in ('\x1b[B', '\x1b[C', '\x1bOB', '\x1bOC'):
                    active_index = (active_index + 1) % 3
                    draw_menu(R_start, active_index)
                # Number key shortcuts: 1 / 2 / 3
                elif event in ('1', '2', '3'):
                    action_idx = int(event) - 1
                    active_index = action_idx
                    draw_menu(R_start, active_index)
                    break_loop, chat = handle_action(action_idx, chat, last_image_filename, combined_name, R_start, old_settings)
                    if break_loop:
                        break
                    R_start, _ = get_cursor_position()
                    print("\n\n\n\n")
                    R_start, _ = get_cursor_position()
                    R_start = max(1, R_start - 5)
                    # handle_action() restored the terminal to cooked/echo mode
                    # (old_settings); re-enter cbreak before re-enabling mouse
                    # reporting, else the incoming mouse escape codes get echoed
                    # to the screen as visible garbage.
                    tty.setcbreak(sys.stdin.fileno())
                    sys.stdout.write("\033[?1003h\033[?1006h\033[?25l")
                    sys.stdout.flush()
                    draw_menu(R_start, active_index)
                elif event.startswith('\x1b[<'):
                    parsed = parse_sgr_mouse(event)
                    if parsed:
                        pb, px, py, is_press = parsed
                        # Button row is the 4th line of the 5-line menu box
                        if py == R_start + 3:
                            clicked_idx = -1
                            if 2 <= px <= 26:
                                clicked_idx = 0
                            elif 28 <= px <= 52:
                                clicked_idx = 1
                            elif 54 <= px <= 78:
                                clicked_idx = 2
                            if clicked_idx != -1:
                                if clicked_idx != active_index:
                                    active_index = clicked_idx
                                    draw_menu(R_start, active_index)
                                # Fire on press (M) so stylus/touch works even
                                # without a release event; ignore drag buttons.
                                if is_press and pb in (0, 1, 2, 64, 65):
                                    break_loop, chat = handle_action(clicked_idx, chat, last_image_filename, combined_name, R_start, old_settings)
                                    if break_loop:
                                        break
                                    R_start, _ = get_cursor_position()
                                    print("\n\n\n\n")
                                    R_start, _ = get_cursor_position()
                                    R_start = max(1, R_start - 5)
                                    # Re-enter cbreak (handle_action left the
                                    # terminal in cooked/echo mode) before
                                    # re-enabling mouse reporting, else mouse
                                    # codes echo to the screen as garbage.
                                    tty.setcbreak(sys.stdin.fileno())
                                    sys.stdout.write("\033[?1003h\033[?1006h\033[?25l")
                                    sys.stdout.flush()
                                    draw_menu(R_start, active_index)
    finally:
        sys.stdout.write("\033[?1003l\033[?1006l\033[?25h")
        sys.stdout.flush()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

# ================= FILE INPUT FALLBACK =================

def open_content_dialog():
    """Open the interactive data-retrieval window for blogpost generation.

    The tkinter window lives in the optional ``_shared.gui`` package (part of the
    author's tools monorepo / cli-tools-kit). In a standalone checkout it won't be
    importable — that's fine: the CLI flags (``--screenshot-path`` /
    ``--image-files`` / ``--text-files`` / ``--raw-text-file``) cover every
    headless path, so we just tell the user to use those instead.
    """
    try:
        from _shared.gui import DataRetrievalWindow, DataRetrievalConfig
    except ImportError:
        print(colored(
            "Interactive content window unavailable (optional _shared.gui package "
            "not installed). Use the CLI flags instead — e.g.\n"
            "  main.py --analyze-only --image-files shot.png\n"
            "  main.py --analyze-only --text-files paper.pdf\n"
            "  main.py --analyze-only --raw-text-file notes.txt\n"
            "See the README for all options.", "yellow"))
        return None
    config = DataRetrievalConfig(
        title="Blogpost Content Input",
        confirm_button_text="Generate Blogpost",
        enable_text_input=True,
        enable_images=True
    )
    return DataRetrievalWindow(config).run()  # Returns dict {'texts': list, 'files': list, 'images': list} or None


def extract_text_from_pdf(pdf_path):
    """Extract raw text from a PDF file."""
    if not HAS_PYPDF2:
        print(colored("PyPDF2 not installed. Install with: pip install PyPDF2", "red"))
        return None

    try:
        text_parts = []
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            print(colored(f"PDF has {len(reader.pages)} pages", "white"))

            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i+1} ---\n{page_text}")

        full_text = "\n\n".join(text_parts)
        print(colored(f"Extracted {len(full_text)} characters from PDF", "green"))
        return full_text

    except Exception as e:
        print(colored(f"Error reading PDF text: {e}", "red"))
        return None


def extract_images_from_pdf(pdf_path, output_dir):
    """
    Extract embedded images from a PDF file.
    Returns list of image paths.
    """
    if not HAS_PYPDF2:
        print(colored("PyPDF2 not installed. Install with: pip install PyPDF2", "red"))
        return []

    try:
        os.makedirs(output_dir, exist_ok=True)

        print(colored(f"Extracting embedded images from PDF...", "cyan"))
        image_paths = []
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        base_name = re.sub(r'[^\w\-]', '_', base_name)[:30]

        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            img_count = 0

            for page_num, page in enumerate(reader.pages):
                # Check if page has images
                if '/XObject' not in page.get('/Resources', {}):
                    continue

                x_objects = page['/Resources']['/XObject'].get_object()

                for obj_name in x_objects:
                    x_obj = x_objects[obj_name]
                    if x_obj['/Subtype'] == '/Image':
                        img_count += 1

                        # Determine image format and extract data
                        try:
                            width = x_obj['/Width']
                            height = x_obj['/Height']

                            # Get the filter type to determine format
                            img_filter = x_obj.get('/Filter', '')
                            if isinstance(img_filter, list):
                                img_filter = img_filter[0] if img_filter else ''

                            data = x_obj.get_data()

                            # Handle different image formats
                            if img_filter == '/DCTDecode':
                                # JPEG
                                ext = 'jpg'
                                img_filename = f"{base_name}_img_{img_count:03d}.{ext}"
                                img_path = os.path.join(output_dir, img_filename)
                                with open(img_path, 'wb') as img_file:
                                    img_file.write(data)

                            elif img_filter == '/FlateDecode':
                                # PNG/raw - need to reconstruct
                                ext = 'png'
                                img_filename = f"{base_name}_img_{img_count:03d}.{ext}"
                                img_path = os.path.join(output_dir, img_filename)

                                color_space = x_obj.get('/ColorSpace', '/DeviceRGB')
                                if isinstance(color_space, list):
                                    color_space = color_space[0]

                                if color_space == '/DeviceRGB':
                                    mode = 'RGB'
                                elif color_space == '/DeviceCMYK':
                                    mode = 'CMYK'
                                elif color_space == '/DeviceGray':
                                    mode = 'L'
                                else:
                                    mode = 'RGB'

                                bits = x_obj.get('/BitsPerComponent', 8)
                                if bits == 1:
                                    mode = '1'

                                try:
                                    img = Image.frombytes(mode, (width, height), data)
                                    if mode == 'CMYK':
                                        img = img.convert('RGB')
                                    img.save(img_path, 'PNG')
                                except Exception:
                                    # If reconstruction fails, skip this image
                                    img_count -= 1
                                    continue

                            elif img_filter == '/JPXDecode':
                                # JPEG2000
                                ext = 'jp2'
                                img_filename = f"{base_name}_img_{img_count:03d}.{ext}"
                                img_path = os.path.join(output_dir, img_filename)
                                with open(img_path, 'wb') as img_file:
                                    img_file.write(data)

                            elif img_filter == '/CCITTFaxDecode':
                                # TIFF/Fax - skip for now as reconstruction is complex
                                img_count -= 1
                                continue

                            else:
                                # Try to save raw data and let PIL figure it out
                                ext = 'png'
                                img_filename = f"{base_name}_img_{img_count:03d}.{ext}"
                                img_path = os.path.join(output_dir, img_filename)
                                try:
                                    from io import BytesIO
                                    img = Image.open(BytesIO(data))
                                    img.save(img_path, 'PNG')
                                except Exception:
                                    img_count -= 1
                                    continue

                            image_paths.append(img_path)
                            print(colored(f"  Saved: {img_filename} ({width}x{height})", "white"))

                        except Exception as e:
                            print(colored(f"  Warning: Could not extract image {img_count}: {e}", "yellow"))
                            img_count -= 1
                            continue

        if image_paths:
            print(colored(f"Extracted {len(image_paths)} embedded images from PDF", "green"))
        else:
            print(colored("No embedded images found in PDF", "yellow"))

        return image_paths

    except Exception as e:
        print(colored(f"Error extracting PDF images: {e}", "red"))
        return []


def read_text_file(file_path):
    """Read raw text from a text-based file."""
    try:
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    text = f.read()
                print(colored(f"Read {len(text)} characters from file (encoding: {encoding})", "green"))
                return text
            except UnicodeDecodeError:
                continue

        print(colored("Could not decode file with common encodings", "red"))
        return None

    except Exception as e:
        print(colored(f"Error reading file: {e}", "red"))
        return None


def get_file_content(file_path, content_dir=None):
    """
    Extract content from a file based on its extension.
    For PDFs, extracts both text and images.
    Returns: (text_content, [image_paths], filename)
    """
    if not file_path or not os.path.exists(file_path):
        return None, [], None

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    print(colored(f"\nProcessing file: {filename}", "cyan"))

    if ext == '.pdf':
        text = extract_text_from_pdf(file_path)
        images = []
        if content_dir:
            images = extract_images_from_pdf(file_path, content_dir)
        return text, images, filename
    else:
        text = read_text_file(file_path)
        return text, [], filename


def take_screenshot():
    """
    Attempt to take a screenshot with Spectacle.
    Returns True if successful, False if cancelled or failed.
    """
    try:
        subprocess.run(["which", "spectacle"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(
            ["spectacle", "-r", "-b", "-n", "-o", TEMP_FILENAME],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if not os.path.exists(TEMP_FILENAME):
            return False  # User cancelled (ESC pressed)
        return True
    except subprocess.CalledProcessError:
        return False


# ================= AI LOGIC =================

def extract_html(text):
    """
    Extract HTML content from LLM response.
    Priority: ```html...``` > <!DOCTYPE...> > <html...>
    """
    # Priority 1: Extract content inside ```html ... ```
    html_block = re.search(r'```html\s*(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if html_block:
        return html_block.group(1).strip()

    # Priority 2: Extract content inside generic ``` ... ``` that looks like HTML
    generic_block = re.search(r'```\s*(<!DOCTYPE.*?</html>)\s*```', text, re.DOTALL | re.IGNORECASE)
    if generic_block:
        return generic_block.group(1).strip()

    # Priority 3: Find <!DOCTYPE html> ... </html>
    doctype_match = re.search(r'(<!DOCTYPE\s+html.*?</html>)', text, re.DOTALL | re.IGNORECASE)
    if doctype_match:
        return doctype_match.group(1).strip()

    # Priority 4: Find <html> ... </html>
    html_match = re.search(r'(<html.*?</html>)', text, re.DOTALL | re.IGNORECASE)
    if html_match:
        return html_match.group(1).strip()

    return None

class StreamingError(Exception):
    """Exception that preserves partial content from interrupted streams."""
    def __init__(self, message, partial_content=""):
        super().__init__(message)
        self.partial_content = partial_content

def stream_response(response_stream, color="green"):
    """Stream and collect response text. Raises StreamingError with partial content on failure."""
    full_text = ""
    try:
        for chunk in response_stream:
            if hasattr(chunk, 'parts') and chunk.parts:
                text_chunk = chunk.text
                print(colored(text_chunk, color), end="", flush=True)
                full_text += text_chunk
    except Exception as e:
        # Wrap the error but preserve what we collected
        raise StreamingError(str(e), partial_content=full_text) from e
    return full_text

def is_transient_error(error_msg):
    """Check if an error is transient and should trigger a fallback."""
    transient_patterns = [
        "429", "ResourceExhausted", "Quota",  # Rate limits
        "500", "503", "Internal",              # Server errors
        "timeout", "Deadline",                 # Timeouts
        "UNAVAILABLE", "overloaded",           # Service issues
    ]
    error_lower = error_msg.lower()
    return any(p.lower() in error_lower for p in transient_patterns)

def generate_blogpost(image_path, image_filename):
    """
    Use Gemini to analyze screenshot and generate HTML blogpost.
    Two-phase approach: 1) Analyze & reason, 2) Generate HTML
    Handles mid-stream failures by continuing with next model.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing from .env file.")

    genai.configure(api_key=GEMINI_API_KEY)

    if not os.path.exists(image_path):
        raise FileNotFoundError("Screenshot file was not found.")

    img = Image.open(image_path)

    # Phase 1: Analysis prompt
    analysis_prompt = """Observe the contents of this image and explain what you see in detail.

YOUR TASK:
1. Describe every visible element - text, diagrams, charts, code, UI elements, etc.
2. Identify the main topic, subject matter, or domain
3. Extract key concepts, technical terms, jargon, or important names
4. Note any data, numbers, relationships, or patterns shown
5. Infer the context - what is this about? Why might someone have captured this?
6. Identify 2-3 aspects that would benefit from deeper exploration or explanation
7. State the dominant language of the visible text on a line of its own, exactly:
   SOURCE_LANGUAGE: <English name of the language, or "none" if the image has no text>

Write this analysis in English regardless of the language in the image - it is
internal working notes, not the blogpost.

Be thorough and analytical. Your analysis will be used to create an insightful blogpost."""

    # Phase 2: HTML generation prompt (will be formatted with image_filename and date)
    todays_date = datetime.now().strftime("%B %d, %Y")  # e.g., "January 16, 2026"

    html_prompt_template = """Based on your analysis above, create a dense, insightful HTML blogpost.

TODAY'S DATE: {todays_date} (use this for any date references in the blogpost)

STEP 1 - PLANNING (think out loud):
Before writing any HTML, plan your approach:
- What sections and structure will best present this content?
- What color scheme and typography fits the domain/topic? (e.g., scientific = clean blues, art = vibrant, code = dark theme)
- Would any interactive elements enhance understanding? Consider:
  * CSS animations (fade-ins, highlights, hover effects)
  * Expandable/collapsible sections for detailed explanations
  * Interactive diagrams or visualizations (SVG, CSS-only charts)
  * Code syntax highlighting if relevant
  * Tooltips for technical terms
- How should the screenshot be presented? (hero image, floating, with annotations?)

STEP 2 - CONTENT REQUIREMENTS:
LANGUAGE:
- Write the blogpost in the language named by SOURCE_LANGUAGE in the analysis.
  A German screenshot gets a German post, a French one a French post.
- If SOURCE_LANGUAGE is "none" or absent, write in English.
- Set the matching <html lang="..."> code (de, en, fr, ...); it is read by the
  blogpost index.
- This applies to everything the reader sees, including the closing quote.
- Expand on the key concepts you identified with deeper context and scientific/technical grounding
- Explain complex topics in an accessible but substantive way
- Make connections to related concepts, history, or applications
- Include the original screenshot prominently as a visual reference
- Write in an engaging, informative style with clear sections

STEP 3 - HTML/STYLING REQUIREMENTS:
- Complete, valid HTML5 document with <!DOCTYPE html>
- Inline CSS in a <style> tag with modern, readable typography
- Implement the styling and interactive elements you planned above
- Responsive design (works on mobile and desktop)
- Include the image with: <img src="{image_filename}" alt="Screenshot">
- Proper meta tags for charset and viewport
- LATEX SUPPORT: Include MathJax for any mathematical content:
  * Add this script in <head>: <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  * Use \\( ... \\) for inline math and \\[ ... \\] for display math
  * NEVER use raw LaTeX without MathJax delimiters

OUTPUT FORMAT:
1. First, briefly outline your structural and styling decisions (2-4 sentences)
2. Then output the complete HTML document wrapped in ```html ... ```
3. Finish the HTML with todays date and a short correlated and signal dense quote, insight or poem. """

    html_prompt = html_prompt_template.format(image_filename=image_filename, todays_date=todays_date)

    # Continuation prompt for when we have partial HTML from a failed stream
    continuation_prompt_template = """The previous generation was interrupted. Here's what was generated so far:

--- PREVIOUS ANALYSIS ---
{analysis}

--- PARTIAL HTML (interrupted) ---
{partial_html}

Please CONTINUE the HTML from exactly where it stopped. Do not restart - just continue writing from the interruption point to complete the document. Make sure to properly close all open tags and complete the HTML structure.

Continue the HTML now (no explanation, just the remaining HTML):"""

    print(colored("\n========== PHASE 1: ANALYZING IMAGE ==========", "cyan", attrs=["bold"]))
    print(colored(f"Image: {image_filename}", "cyan"))
    print(colored("===============================================\n", "cyan", attrs=["bold"]))

    # Track state across model fallbacks
    completed_analysis = None
    partial_html = None
    chat = None

    # Model fallback loop
    for model_idx, model_name in enumerate(GEMINI_CANDIDATE_MODELS):
        try:
            print(colored(f"\n[TRYING MODEL: {model_name}]", "white", attrs=["bold"]))
            model = genai.GenerativeModel(model_name)

            # Start a chat session for multi-turn conversation
            chat = model.start_chat(history=[])

            # Phase 1: Analysis (skip if we already have it from a previous model)
            if completed_analysis is None:
                print(colored("\n--- Analysis ---", "yellow", attrs=["bold"]))
                response1 = chat.send_message(
                    [analysis_prompt, img],
                    stream=True,
                    safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
                )

                analysis_text = stream_response(response1, "yellow")

                if not analysis_text.strip():
                    raise ValueError("Empty analysis response (possibly content filtered)")

                completed_analysis = analysis_text
            else:
                # We have analysis from previous model - inject it into chat history
                print(colored("\n--- Using previous analysis ---", "yellow", attrs=["bold"]))
                print(colored(completed_analysis[:500] + "..." if len(completed_analysis) > 500 else completed_analysis, "yellow"))

                # Send the analysis context to establish chat history
                chat.send_message(
                    [analysis_prompt, img],
                    stream=False,
                    safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
                )

            # Phase 2: Generate HTML (or continue from partial)
            print(colored("\n\n========== PHASE 2: GENERATING HTML ==========", "cyan", attrs=["bold"]))
            print(colored("===============================================\n", "cyan", attrs=["bold"]))

            if partial_html and len(partial_html) > 100:
                # We have partial HTML from a previous failed attempt - ask to continue
                print(colored("--- Continuing interrupted generation ---", "magenta", attrs=["bold"]))
                print(colored(f"[Partial HTML: {len(partial_html)} chars collected before failure]", "magenta"))

                continuation_prompt = continuation_prompt_template.format(
                    analysis=completed_analysis[:2000],  # Truncate for context limit
                    partial_html=partial_html
                )

                response2 = chat.send_message(
                    continuation_prompt,
                    stream=True,
                    safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
                )

                continuation = stream_response(response2, "green")
                print(colored("\n===============================================", "green", attrs=["bold"]))

                # Combine partial + continuation
                html_response = partial_html + continuation
            else:
                # Fresh HTML generation
                print(colored("--- HTML Generation ---", "green", attrs=["bold"]))
                response2 = chat.send_message(
                    html_prompt,
                    stream=True,
                    safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
                )

                html_response = stream_response(response2, "green")
                print(colored("\n===============================================", "green", attrs=["bold"]))

            if not html_response.strip():
                raise ValueError("Empty HTML response (possibly content filtered)")

            html_content = extract_html(html_response)
            if html_content:
                return html_content, chat
            else:
                print(colored("\nWarning: Could not extract HTML from response. Trying next model...", "yellow"))
                continue

        except StreamingError as e:
            # Streaming failed mid-way - preserve partial content
            error_msg = str(e)
            print(colored(f"\n[!] STREAM INTERRUPTED: {error_msg[:80]}...", "red"))

            # Check if this was during HTML generation (we have analysis but failed during phase 2)
            if completed_analysis and e.partial_content:
                partial_html = (partial_html or "") + e.partial_content
                print(colored(f"[!] Preserved {len(e.partial_content)} chars of partial HTML. Will continue with next model.", "yellow"))

            if model_idx < len(GEMINI_CANDIDATE_MODELS) - 1:
                print(colored(f"[!] Falling back to next model...", "yellow"))
                continue
            else:
                # Last model failed - try to salvage what we have
                if partial_html:
                    html_content = extract_html(partial_html)
                    if html_content:
                        print(colored("[!] Salvaged partial HTML from interrupted stream.", "yellow"))
                        return html_content, chat
                raise RuntimeError(f"All models failed. Last error: {error_msg}")

        except Exception as e:
            error_msg = str(e)

            # Check for transient/retryable errors
            if is_transient_error(error_msg):
                print(colored(f"\n[!] TRANSIENT ERROR for {model_name}: {error_msg[:60]}...", "yellow"))
                if model_idx < len(GEMINI_CANDIDATE_MODELS) - 1:
                    print(colored("[!] Trying next model...", "yellow"))
                    continue
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(colored(f"\n[!] MODEL NOT FOUND: {model_name}. Skipping...", "yellow"))
                continue
            elif "Empty" in error_msg or "content filtered" in error_msg.lower():
                print(colored(f"\n[!] CONTENT FILTERED for {model_name}. Trying next model...", "yellow"))
                continue
            elif "Invalid operation" in error_msg and "response.text" in error_msg:
                print(colored(f"\n[!] NO VALID PARTS IN RESPONSE for {model_name}. Trying next model...", "yellow"))
                continue
            else:
                raise e

    raise RuntimeError("All models failed. Check your API quota and network connection.")

def save_and_open_blogpost(html_content, temp_screenshot, image_filename):
    """
    Save HTML and screenshot to blogpost directory, then open in browser.

    Args:
        html_content: The generated HTML string
        temp_screenshot: Path to the temporary screenshot file
        image_filename: The image filename used in the HTML (e.g., screenshot_20260116_123456.png)
    """
    # Extract timestamp from image filename for a stable per-post folder name.
    # image_filename is like "screenshot_20260116_123456.png"
    timestamp = image_filename.replace("screenshot_", "").replace(".png", "")
    post_dir = _session_post_dir(f"blogpost_{timestamp}")

    img_path = os.path.join(post_dir, image_filename)
    html_path = os.path.join(post_dir, "index.html")

    # Copy screenshot
    shutil.copy(temp_screenshot, img_path)
    print(colored(f"Saved image: {img_path}", "cyan"))

    html_content = _record_provenance(post_dir, html_content)

    # Save HTML
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(colored(f"Saved HTML: {html_path}", "cyan"))

    # Open in browser
    print(colored(f"\nOpening in browser...", "blue"))
    try:
        webbrowser.register('firefox_custom', None, webbrowser.BackgroundBrowser(BROWSER_PATH))
        browser = webbrowser.get('firefox_custom')
    except:
        browser = webbrowser.get()

    browser.open(f"file://{html_path}")

    return html_path

def _rmdir_if_temp(path):
    """Remove a per-invocation mkdtemp dir once emptied, so /tmp doesn't
    accumulate one bloggen_* dir per process."""
    parent = os.path.dirname(path)
    if os.path.basename(parent).startswith("bloggen_"):
        try:
            os.rmdir(parent)
        except OSError:
            pass


def cleanup(screenshot_path=None):
    path = screenshot_path or TEMP_FILENAME
    if os.path.exists(path):
        os.remove(path)
    _rmdir_if_temp(path)
    # The child also mkdtemp'd its own (unused) dir at import — drop it too.
    _rmdir_if_temp(TEMP_FILENAME)


def analyze_content_and_images(text_content, image_paths, source_name):
    """
    First LLM call: Analyze all text and images, generate descriptions/filenames for each image.
    Returns: (analysis_text, image_descriptions) where image_descriptions is a list of dicts
             with 'original_path', 'filename', 'description'
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing from .env file.")

    genai.configure(api_key=GEMINI_API_KEY)

    # Prepare image objects
    images = []
    for img_path in image_paths:
        if os.path.exists(img_path):
            images.append(Image.open(img_path))

    # Build the analysis prompt
    image_section = ""
    if images:
        image_section = f"\n\nYou are also provided with {len(images)} images to analyze."

    analysis_prompt = f"""You are analyzing content for a blogpost.

SOURCE: {source_name}

=== TEXT CONTENT ===
{text_content[:30000] if text_content else "(No text content)"}
=== END TEXT ==={image_section}

YOUR TASKS:
1. Analyze all text content - identify main topics, key concepts, technical terms
2. For EACH image provided, output a structured description in this exact format:

IMAGE_DESCRIPTIONS_START
{{
  "images": [
    {{"index": 1, "suggested_filename": "descriptive_name.png", "description": "What this image shows and its relevance"}},
    ...
  ]
}}
IMAGE_DESCRIPTIONS_END

3. After the image descriptions, provide a comprehensive content analysis covering:
   - Main subject matter and domain
   - Key concepts and their relationships
   - Notable data, figures, or findings
   - Context and significance
   - 2-3 angles for deeper exploration in the blogpost
   - The dominant language of the source text, on a line of its own, exactly:
     SOURCE_LANGUAGE: <English name of the language, or "none" if there is no text>

Write this analysis in English regardless of the language of the source - it is
internal working notes, not the blogpost.

Be thorough - your analysis drives the blogpost generation."""

    print(colored("\n========== PHASE 1: ANALYZING CONTENT & IMAGES ==========", "cyan", attrs=["bold"]))
    print(colored(f"Source: {source_name}", "cyan"))
    print(colored(f"Text length: {len(text_content) if text_content else 0} chars", "cyan"))
    print(colored(f"Images: {len(images)}", "cyan"))
    print(colored("==========================================================\n", "cyan", attrs=["bold"]))

    for model_idx, model_name in enumerate(GEMINI_CANDIDATE_MODELS):
        try:
            print(colored(f"\n[TRYING MODEL: {model_name}]", "white", attrs=["bold"]))
            model = genai.GenerativeModel(model_name)

            # Build message content - text prompt + all images
            message_content = [analysis_prompt] + images

            response = model.generate_content(
                message_content,
                stream=True,
                safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
            )

            analysis_text = stream_response(response, "yellow")

            if not analysis_text.strip():
                raise ValueError("Empty analysis response")

            # Parse image descriptions from response
            image_descriptions = []
            desc_match = re.search(r'IMAGE_DESCRIPTIONS_START\s*(\{.*?\})\s*IMAGE_DESCRIPTIONS_END', analysis_text, re.DOTALL)
            if desc_match:
                try:
                    desc_json = json.loads(desc_match.group(1))
                    for i, desc in enumerate(desc_json.get('images', [])):
                        if i < len(image_paths):
                            image_descriptions.append({
                                'original_path': image_paths[i],
                                'filename': desc.get('suggested_filename', f'image_{i+1}.png'),
                                'description': desc.get('description', '')
                            })
                except json.JSONDecodeError:
                    print(colored("Warning: Could not parse image descriptions JSON", "yellow"))

            # Fill in any missing descriptions
            for i, img_path in enumerate(image_paths):
                if i >= len(image_descriptions):
                    image_descriptions.append({
                        'original_path': img_path,
                        'filename': f'image_{i+1}.png',
                        'description': f'Image {i+1} from {source_name}'
                    })

            return analysis_text, image_descriptions, message_content

        except Exception as e:
            error_msg = str(e)
            if is_transient_error(error_msg) and model_idx < len(GEMINI_CANDIDATE_MODELS) - 1:
                print(colored(f"\n[!] TRANSIENT ERROR: {error_msg[:60]}... Trying next model...", "yellow"))
                continue
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(colored(f"\n[!] MODEL NOT FOUND: {model_name}. Skipping...", "yellow"))
                continue
            elif model_idx < len(GEMINI_CANDIDATE_MODELS) - 1:
                print(colored(f"\n[!] ERROR: {error_msg[:60]}... Trying next model...", "yellow"))
                continue
            else:
                raise

    raise RuntimeError("All models failed during content analysis.")


def generate_blogpost_from_content(text_content, image_descriptions, analysis_text, source_name, message_content=None):
    """
    Generate HTML blogpost from analyzed content with multiple images.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing from .env file.")

    genai.configure(api_key=GEMINI_API_KEY)

    todays_date = datetime.now().strftime("%B %d, %Y")

    # Build image reference section for the prompt
    image_refs = ""
    if image_descriptions:
        image_refs = "\n\nIMAGES AVAILABLE FOR THE BLOGPOST:\n"
        for desc in image_descriptions:
            image_refs += f"- {desc['filename']}: {desc['description']}\n"
        image_refs += "\nInclude these images appropriately in your HTML using <img src=\"FILENAME\" alt=\"DESCRIPTION\">"

    html_prompt = f"""Based on the analysis below, create a dense, insightful HTML blogpost.

TODAY'S DATE: {todays_date}

=== PREVIOUS ANALYSIS ===
{analysis_text[:15000]}
=== END ANALYSIS ==={image_refs}

STEP 1 - PLANNING (think out loud):
Before writing any HTML, plan your approach:
- What sections and structure will best present this content?
- What color scheme and typography fits the domain/topic?
- Would any interactive elements enhance understanding? Consider:
  * CSS animations (fade-ins, highlights, hover effects)
  * Expandable/collapsible sections for detailed explanations
  * Code syntax highlighting if relevant
  * Tooltips for technical terms
- How should the images be integrated? (gallery, inline, with captions?)

STEP 2 - CONTENT REQUIREMENTS:
LANGUAGE:
- Write the blogpost in the language named by SOURCE_LANGUAGE in the analysis.
  A German screenshot gets a German post, a French one a French post.
- If SOURCE_LANGUAGE is "none" or absent, write in English.
- Set the matching <html lang="..."> code (de, en, fr, ...); it is read by the
  blogpost index.
- This applies to everything the reader sees, including the closing quote.
- Expand on the key concepts with deeper context and scientific/technical grounding
- Explain complex topics in an accessible but substantive way
- Make connections to related concepts, history, or applications
- Write in an engaging, informative style with clear sections

STEP 3 - HTML/STYLING REQUIREMENTS:
- Complete, valid HTML5 document with <!DOCTYPE html>
- Inline CSS in a <style> tag with modern, readable typography
- Implement the styling and interactive elements you planned above
- Responsive design (works on mobile and desktop)
- Proper meta tags for charset and viewport
- Include images with appropriate styling and captions
- LATEX SUPPORT: Include MathJax for any mathematical content:
  * Add this script in <head>: <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
  * Use \\( ... \\) for inline math and \\[ ... \\] for display math
  * NEVER use raw LaTeX without MathJax delimiters

OUTPUT FORMAT:
1. First, briefly outline your structural and styling decisions (2-4 sentences)
2. Then output the complete HTML document wrapped in ```html ... ```
3. Finish the HTML with todays date and a short correlated and signal dense quote, insight or poem. """

    print(colored("\n\n========== PHASE 2: GENERATING HTML ==========", "cyan", attrs=["bold"]))
    print(colored("===============================================\n", "cyan", attrs=["bold"]))

    history = []
    if message_content and analysis_text:
        history = [
            {"role": "user", "parts": message_content},
            {"role": "model", "parts": [analysis_text]}
        ]

    chat = None
    for model_idx, model_name in enumerate(GEMINI_CANDIDATE_MODELS):
        try:
            print(colored(f"\n[TRYING MODEL: {model_name}]", "white", attrs=["bold"]))
            model = genai.GenerativeModel(model_name)
            chat = model.start_chat(history=history)

            response = chat.send_message(
                html_prompt,
                stream=True,
                safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
            )

            html_response = stream_response(response, "green")
            print(colored("\n===============================================", "green", attrs=["bold"]))

            if not html_response.strip():
                raise ValueError("Empty HTML response")

            html_content = extract_html(html_response)
            if html_content:
                return html_content, chat
            else:
                print(colored("\nWarning: Could not extract HTML. Trying next model...", "yellow"))
                continue

        except Exception as e:
            error_msg = str(e)
            if is_transient_error(error_msg) and model_idx < len(GEMINI_CANDIDATE_MODELS) - 1:
                print(colored(f"\n[!] TRANSIENT ERROR: {error_msg[:60]}... Trying next model...", "yellow"))
                continue
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(colored(f"\n[!] MODEL NOT FOUND: {model_name}. Skipping...", "yellow"))
                continue
            elif model_idx < len(GEMINI_CANDIDATE_MODELS) - 1:
                print(colored(f"\n[!] ERROR: {error_msg[:60]}... Trying next model...", "yellow"))
                continue
            else:
                raise

    raise RuntimeError("All models failed during HTML generation.")


def save_and_open_blogpost_content(html_content, image_descriptions, source_name):
    """
    Save HTML and all images to blogpost directory, then open in browser.
    Returns the HTML path.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = re.sub(r'[^\w\-]', '_', source_name)[:30]
    post_dir = _session_post_dir(f"blogpost_{base_name}_{timestamp}")
    html_path = os.path.join(post_dir, "index.html")

    # Copy all images into this post's folder, next to index.html
    for desc in image_descriptions:
        src_path = desc['original_path']
        dst_filename = desc['filename']
        dst_path = os.path.join(post_dir, dst_filename)
        if os.path.exists(src_path):
            shutil.copy(src_path, dst_path)
            print(colored(f"Saved image: {dst_filename}", "cyan"))

    html_content = _record_provenance(post_dir, html_content)

    # Save HTML
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(colored(f"Saved HTML: {html_path}", "cyan"))

    # Open in browser
    print(colored(f"\nOpening in browser...", "blue"))
    try:
        webbrowser.register('firefox_custom', None, webbrowser.BackgroundBrowser(BROWSER_PATH))
        browser = webbrowser.get('firefox_custom')
    except:
        browser = webbrowser.get()

    browser.open(f"file://{html_path}")

    return html_path


def main():
    args = parse_arguments()

    # --install / --remove / --install-skill / --uninstall-skill are all handled
    # up top, before the heavy imports, so execution never reaches here for them.

    # Remember what this run was fed, so the saved post can say where it came
    # from. --screenshot-path/--raw-text-file are usually temp files; recording
    # them is still truthful, and the cwd is what carries the real signal.
    global _SOURCE_INPUTS, _SOURCE_DECLARED
    _SOURCE_INPUTS = [p for p in ([args.screenshot_path, args.raw_text_file]
                                  + list(args.text_files or [])
                                  + list(args.image_files or [])) if p]
    _SOURCE_DECLARED = list(args.source or [])

    # Track usage
    try:
        from _shared.usage_tracker import track_usage_auto
        track_usage_auto(__file__)
    except ImportError:
        pass

    if args.analyze_only:
        try:
            # Check if we're processing content from files/text or a screenshot
            if args.text_files is not None or args.image_files is not None or args.raw_text_file:
                # Content mode: process text, PDFs, and images
                all_text = []
                all_images = []
                source_names = []

                # Scratch dir for PDF-extracted images. When we own it (no
                # parent-supplied path) put it in the system tempdir, NOT under
                # blogposts/ — the images that matter get copied into the post
                # folder by save_and_open_blogpost_content; this stays disposable.
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                content_dir = args.content_dir
                _own_content_dir = not content_dir
                if not content_dir:
                    content_dir = _tempfile.mkdtemp(prefix="bloggen_content_")
                os.makedirs(content_dir, exist_ok=True)

                # Process raw pasted text
                if args.raw_text_file and os.path.exists(args.raw_text_file):
                    try:
                        with open(args.raw_text_file, 'r', encoding='utf-8') as f:
                            raw_text = f.read().strip()
                        if raw_text:
                            all_text.append(f"=== PASTED TEXT ===\n{raw_text}")
                            source_names.append("pasted_text")
                            print(colored(f"Loaded {len(raw_text)} characters of pasted text", "green"))
                        os.remove(args.raw_text_file)
                    except Exception as e:
                        print(colored(f"Warning: Could not read pasted text: {e}", "yellow"))

                # Process text/PDF files
                if args.text_files:
                    for file_path in args.text_files:
                        text_content, images, source_filename = get_file_content(file_path, content_dir)
                        if text_content:
                            all_text.append(f"=== FILE: {source_filename} ===\n{text_content}")
                            source_names.append(source_filename)
                        if images:
                            all_images.extend(images[:5]) # !TODO: Find a better approach than limiting the images

                # Process direct image files
                if args.image_files:
                    for img_path in args.image_files:
                        if os.path.exists(img_path):
                            all_images.append(img_path)
                            source_names.append(os.path.basename(img_path))
                            print(colored(f"Added image: {os.path.basename(img_path)}", "green"))

                if not all_text and not all_images:
                    print(colored("No content to process.", "red"))
                    manual_hold_on_crash()
                    return

                # Combine sources for naming
                combined_name = "_".join(source_names[:3])
                if len(source_names) > 3:
                    combined_name += f"_and_{len(source_names)-3}_more"

                combined_text = "\n\n".join(all_text)

                print(colored(f"\nProcessing {len(source_names)} source(s):", "cyan"))
                for name in source_names:
                    print(colored(f"  - {name}", "white"))
                print(colored(f"Total images: {len(all_images)}", "cyan"))

                # Phase 1: Analyze content and get image descriptions
                analysis_text, image_descriptions, message_content = analyze_content_and_images(
                    combined_text, all_images, combined_name
                )

                # Phase 2: Generate blogpost HTML
                html_content, chat = generate_blogpost_from_content(
                    combined_text, image_descriptions, analysis_text, combined_name, message_content
                )

                if html_content is None:
                    print(colored("Failed to generate HTML content.", "red"))
                    manual_hold_on_crash()
                    return

                # Save and open
                save_and_open_blogpost_content(html_content, image_descriptions, combined_name)

                # Drop the scratch dir entirely (images already copied into the
                # post folder). Only remove one we created, never a parent's.
                try:
                    if _own_content_dir and content_dir and os.path.exists(content_dir):
                        shutil.rmtree(content_dir, ignore_errors=True)
                except Exception:
                    pass

                run_interactive_loop(chat, image_descriptions[0]['filename'] if image_descriptions else None, combined_name)

            else:
                # Screenshot mode (default)
                # Use the path the parent process actually saved to; only fall
                # back to this process's own TEMP_FILENAME when run standalone.
                screenshot_path = args.screenshot_path or TEMP_FILENAME
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"screenshot_{timestamp}.png"

                # Generate blogpost from screenshot
                html_content, chat = generate_blogpost(screenshot_path, image_filename)

                if html_content is None:
                    print(colored("Failed to generate HTML content.", "red"))
                    manual_hold_on_crash()
                    return

                # Save and open
                save_and_open_blogpost(html_content, screenshot_path, image_filename)

                # Cleanup and countdown
                cleanup(screenshot_path)
                run_interactive_loop(chat, image_filename, image_filename.replace(".png", ""))

        except Exception as e:
            print(colored(f"\nCRITICAL ERROR: {str(e)}", "red", attrs=["bold"]))
            traceback.print_exc()
            manual_hold_on_crash()
        return

    # Main flow: take screenshot, or fall back to content input dialog
    screenshot_taken = take_screenshot()

    if screenshot_taken:
        # Screenshot captured successfully - launch terminal for analysis
        launch_terminal_process()
    else:
        # Screenshot cancelled/failed - open content input window as fallback
        print(colored("Screenshot cancelled. Opening content input window...", "yellow"))
        result = open_content_dialog()

        if result:
            python_exec = sys.executable
            script_path = os.path.abspath(__file__)
            cmd = ["konsole", "-e", python_exec, script_path, "--analyze-only"]

            # Handle pasted texts - save to temp file
            if result.get('texts'):
                combined_texts = "\n\n=== TEXT ENTRY ===\n".join(result['texts'])
                temp_text_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
                temp_text_file.write(combined_texts)
                temp_text_file.close()
                cmd.extend(["--raw-text-file", temp_text_file.name])

            # Handle document files (PDFs, text files)
            if result.get('files'):
                cmd.append("--text-files")
                cmd.extend(result['files'])

            # Handle image files
            if result.get('images'):
                cmd.append("--image-files")
                cmd.extend(result['images'])

            subprocess.Popen(cmd)
        else:
            print(colored("No content provided. Exiting.", "yellow"))


if __name__ == "__main__":
    main()
