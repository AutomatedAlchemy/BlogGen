#!/usr/bin/env python3
"""Where posts are written.

`BLOGGEN_OUTPUT_DIR` names the folder. It is read from the environment, then
from the `.env` the tool uses. Without it posts go to `blogposts/` beside the
tool.

The `.env` is found in main.py's order: `BLOGGEN_ENV`, `SCREENSHOT_BLOGPOST_ENV`,
the one beside the tool, then the nearest one in a parent folder. python-dotenv
parses it, as in main.py. publish.py and build_index.py also run without
python-dotenv; then only the environment variable counts, and a note says so
when the `.env` sets the variable.
"""

import os
import sys

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


def _names_the_variable(path):
    """Whether the .env at *path* mentions VAR at all."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return VAR in handle.read()
    except OSError:
        return False


def _from_env_file(path):
    """The value of VAR in the .env at *path*, read by python-dotenv as main.py reads it.

    One parser, so the three scripts cannot disagree about the folder. Without
    python-dotenv the file is not read; a note says so when the file sets VAR.
    """
    try:
        from dotenv import dotenv_values
    except ImportError:
        if _names_the_variable(path):
            print(f"note: {path} sets {VAR}, but python-dotenv is not installed, so the "
                  "value is ignored. Install python-dotenv or export the variable.",
                  file=sys.stderr)
        return ""
    try:
        return dotenv_values(path).get(VAR) or ""
    except OSError:
        return ""


def blogpost_dir(script_dir):
    """The folder posts are written to, as an absolute path."""
    value = os.environ.get(VAR)
    if not value:
        env_file = _env_file(script_dir)
        value = _from_env_file(env_file) if env_file else ""
    if not value:
        return os.path.join(script_dir, "blogposts")
    # A relative value counts from the tool's folder, not from the current
    # directory, which differs between runs.
    return os.path.abspath(os.path.join(script_dir, os.path.expanduser(value)))
