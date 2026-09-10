# BlogGen

Turn a screenshot, image(s), PDF, pasted text, or the current conversation into a
**self-contained, styled HTML blogpost** — Gemini analyses the supplied content, then generates a complete
HTML5 article (inline responsive CSS, optional MathJax) that expands on the
concepts it found. The result is written to disk and opened in your browser.

**See one:** [a full, rendered post](https://probable.work/bloggen/example/) — generated
from a single screenshot, served exactly as the tool wrote it.

> _A short demo GIF / video will live here._
<!-- ![demo](assets/demo.gif) -->

## How it works

Two phases, both Gemini:

1. **Analyse** the inputs (text + images extracted from PDFs, raw images, or
   pasted text).
2. **Generate** a self-contained blogpost into its own folder
   `blogposts/<name>/` — an `index.html` plus any referenced images — then
   open it in the browser.

## Install

```bash
pip install -r requirements.txt
```

Set a Gemini API key — either export it or drop a `.env` next to `main.py`:

```bash
export GEMINI_API_KEY=...           # or:
echo 'GEMINI_API_KEY=...' > .env
```

Optional `.env` knobs:

| Variable | Purpose | Default |
|----------|---------|---------|
| `GEMINI_API_KEY` | **required** — Gemini API key | — |
| `COMPETENT_GEMINI_MODELS`, `STRONG_GEMINI_MODELS` | comma-separated fallback model lists, tried after the preferred model | built-in fallbacks |
| `BROWSER_PATH` | browser to open the result | `/usr/bin/firefox` |
| `BLOGGEN_ENV` | explicit path to a `.env` file | — |

The preferred model is `gemini-3.6-flash`; the env model lists (and a small
built-in list) act as fallbacks.

## Usage

```bash
# From one or more images
python main.py --analyze-only --image-files a.png b.jpg

# From a PDF (extracts its text AND embedded images)
python main.py --analyze-only --text-files paper.pdf

# From a single screenshot (screenshot-specific prompt + hero image)
python main.py --analyze-only --screenshot-path shot.png

# From literal text — write it to a file first
printf '%s' "the text to write up" > /tmp/sb_text.txt
python main.py --analyze-only --raw-text-file /tmp/sb_text.txt

# Mix any of the above in one post
python main.py --analyze-only --text-files notes.pdf --image-files fig1.png --raw-text-file /tmp/sb_text.txt
```

The tool prints `Saved HTML: <path>` for the generated file.

## Provenance — where a post came from

Every publish writes `blogposts/<name>/source.json` and stamps the same record
into the HTML head as `<meta name="bloggen:provenance">` (the sidecar is easy to
read; the meta tag survives the folder being moved). It records the working
directory, the git repo + branch + commit if there is one, the input files, the
host and the mode (`gemini` or `agent`).

So **run bloggen from the project the post is about** — that is the signal that
makes "which posts came out of my mujoco training?" answerable later. When the
origin is more specific than the cwd, or isn't a file at all, name it:

```bash
python publish.py --html post.html --source .state/status.html
python main.py --analyze-only --text-files paper.pdf --source https://arxiv.org/abs/…
```

The index page turns each recorded source into a filter chip and a clickable
tag on the card. Posts published before this existed simply carry no source;
nothing is guessed for them.

## Index page over everything you've published

`build_index.py` scans `blogposts/` and writes a single static page,
`blogposts/index.html`, that links to every post:

```bash
python build_index.py            # regenerate
python build_index.py --open     # …and open it
```

It reads each post's `<title>`, headings, first paragraphs and full body text,
embeds the whole corpus inline and ranks queries client-side with **BM25F** —
four weighted fields (title 8× · headings 3× · description 2× · body 1×), prefix
expansion for partial words, accent folding (`wohler` finds `Wöhler`) and a
phrase bonus. Works straight off `file://`: no server, no network, no
dependencies beyond the standard library.

The page is a two-pane layout — a scrollable result list plus a live preview
iframe on wide screens, list-only below 1024 px — and never produces a
page-level scrollbar; only the inner panes scroll. Legacy loose
`blogposts/blogpost_*.html` files are indexed too, and ones that are
byte-identical to a `<slug>/index.html` are dropped as duplicates.

Re-run it after publishing; the page is regenerated from scratch each time.

## Optional desktop / Claude-Code integration

- `python main.py --install` registers a desktop launcher (and the Claude Code
  skill). This needs the [`cli-tools-kit`](https://github.com/Probst1nator/cli-tools-kit)
  package; blogpost generation itself works without it via the CLI flags above.
- `python main.py --install-skill` / `--uninstall-skill` register a Claude Code
  `bloggen` skill (`~/.claude/skills/bloggen/SKILL.md`).
- Running with no flags opens an interactive tkinter content window if the
  optional `_shared.gui` package is available; otherwise it points you to the
  CLI flags.

## License

MIT — see [LICENSE](LICENSE).
