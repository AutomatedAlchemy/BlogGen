#!/usr/bin/env python3
"""Where posts are written.

`BLOGGEN_OUTPUT_DIR` names the folder. It is read from the environment, then
from the `.env` the tool uses. Without it posts go to `blogposts/` beside the
tool.

The `.env` is found in main.py's order: `BLOGGEN_ENV`, `SCREENSHOT_BLOGPOST_ENV`,
the one beside the tool, then the nearest one in a parent folder. python-dotenv
parses it when it is installed. publish.py and build_index.py also run without
it, so a small reader for this one line stands in.
"""

import os

VAR = "BLOGGEN_OUTPUT_DIR"


def _env_file(script_dir):
    """The .env main.py would load, or '' when there is none."""
    override = os.environ.get("BLOGGEN_ENV") or os.environ.get("SCREENSHOT_BLOGPOST_ENV")
    if override:
        return override
    folder = os.path.abspath(script_dir)
    while True:
        candidate = os.path.join(folder, ".env")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(folder)
        if parent == folder:
            return ""
        folder = parent


def _parse_value(raw):
    """The value of one `KEY=value` line: quotes removed, an inline comment dropped."""
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        end = raw.find(raw[0], 1)
        return raw[1:end] if end > 0 else raw[1:]
    return raw.split(" #", 1)[0].strip()


def _from_env_file(path):
    """The value of VAR in the .env at *path*, or '' when the file or the line is missing."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        dotenv_values = None
    if dotenv_values is not None:
        try:
            return dotenv_values(path).get(VAR) or ""
        except OSError:
            return ""
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                key, sep, value = line.strip().partition("=")
                if sep and key.removeprefix("export ").strip() == VAR:
                    return _parse_value(value)
    except OSError:
        pass
    return ""


def blogpost_dir(script_dir):
    """The folder posts are written to, as an absolute path."""
    value = os.environ.get(VAR)
    if not value:
        env_file = _env_file(script_dir)
        value = _from_env_file(env_file) if env_file else ""
    if not value:
        return os.path.join(script_dir, "blogposts")
    return os.path.abspath(os.path.expanduser(value))
