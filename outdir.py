#!/usr/bin/env python3
"""Where posts are written.

`BLOGGEN_OUTPUT_DIR` names the folder. It is read from the environment, then
from the `.env` the tool uses (`BLOGGEN_ENV`, else the one beside `main.py`).
Without it posts go to `blogposts/` beside the tool.

Stdlib only, so publish.py and build_index.py can use it without python-dotenv.
"""

import os

VAR = "BLOGGEN_OUTPUT_DIR"


def _from_env_file(path):
    """The value of VAR in the .env at *path*, or '' when the file or the line is missing."""
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                key, sep, value = line.strip().partition("=")
                if sep and key.removeprefix("export ").strip() == VAR:
                    return value.strip().strip("'\"")
    except OSError:
        pass
    return ""


def blogpost_dir(script_dir):
    """The folder posts are written to, as an absolute path."""
    env_file = os.environ.get("BLOGGEN_ENV") or os.path.join(script_dir, ".env")
    value = os.environ.get(VAR) or _from_env_file(env_file)
    if not value:
        return os.path.join(script_dir, "blogposts")
    return os.path.abspath(os.path.expanduser(value))
