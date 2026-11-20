"""Tests for the output folder: BLOGGEN_OUTPUT_DIR, from the environment or the .env."""

import os
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

import outdir  # noqa: E402


def test_default_is_blogposts_beside_the_tool(tmp_path, monkeypatch):
    monkeypatch.delenv(outdir.VAR, raising=False)
    monkeypatch.delenv("BLOGGEN_ENV", raising=False)
    assert outdir.blogpost_dir(str(tmp_path)) == str(tmp_path / "blogposts")


def test_environment_wins_and_expands_the_home_folder(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"{outdir.VAR}=/from/the/file\n")
    monkeypatch.delenv("BLOGGEN_ENV", raising=False)
    monkeypatch.setenv(outdir.VAR, "~/posts")
    assert outdir.blogpost_dir(str(tmp_path)) == os.path.expanduser("~/posts")


def test_env_file_is_read_without_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv(outdir.VAR, raising=False)
    other = tmp_path / "shared.env"
    other.write_text(f'GEMINI_API_KEY=x\nexport {outdir.VAR}="{tmp_path}/out"\n')
    monkeypatch.setenv("BLOGGEN_ENV", str(other))
    assert outdir.blogpost_dir(str(tmp_path / "tool")) == str(tmp_path / "out")
