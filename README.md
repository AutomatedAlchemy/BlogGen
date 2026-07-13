# BlogGen

Turn a screenshot, image(s), PDF, pasted text, or the current conversation into a
**self-contained, styled HTML blogpost** — Gemini analyses the supplied content, then generates a complete
HTML5 article (inline responsive CSS, optional MathJax) that expands on the
concepts it found. The result is written to disk and opened in your browser.

> _A short demo GIF / video will live here._
<!-- ![demo](assets/demo.gif) -->

## How it works

Two phases, both Gemini:

1. **Analyse** the inputs (text + images extracted from PDFs, raw images, or
   pasted text).
2. **Generate** a single self-contained `blogpost_<timestamp>.html` (plus any
   referenced images) under `blogposts/`, then open it in the browser.

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

The preferred model is `gemini-3.5-flash`; the env model lists (and a small
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

## Optional desktop / Claude-Code integration

- `python main.py --install` registers a desktop launcher (and the Claude Code
  skill). This needs the [`cli-tool-kit`](https://github.com/Probst1nator/cli-tool-kit)
  package; blogpost generation itself works without it via the CLI flags above.
- `python main.py --install-skill` / `--uninstall-skill` register a Claude Code
  `bloggen` skill (`~/.claude/skills/bloggen/SKILL.md`).
- Running with no flags opens an interactive tkinter content window if the
  optional `_shared.gui` package is available; otherwise it points you to the
  CLI flags.

## License

MIT — see [LICENSE](LICENSE).
