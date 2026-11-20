"""Tests for the output folder: BLOGGEN_OUTPUT_DIR, from the environment or the .env."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

import outdir  # noqa: E402


def _no_env(monkeypatch):
    for name in (outdir.VAR, "BLOGGEN_ENV", "SCREENSHOT_BLOGPOST_ENV"):
        monkeypatch.delenv(name, raising=False)


def test_default_is_blogposts_beside_the_tool(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    monkeypatch.setattr(outdir, "_env_file", lambda script_dir: "")
    assert outdir.blogpost_dir(str(tmp_path)) == str(tmp_path / "blogposts")


def test_environment_wins_and_expands_the_home_folder(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    (tmp_path / ".env").write_text(f"{outdir.VAR}=/from/the/file\n")
    monkeypatch.setenv(outdir.VAR, "~/posts")
    assert outdir.blogpost_dir(str(tmp_path)) == os.path.expanduser("~/posts")


# The .env cases need python-dotenv, like main.py. The other tests run without it.
needs_dotenv = pytest.mark.skipif(importlib.util.find_spec("dotenv") is None,
                                  reason="python-dotenv is not installed")


@needs_dotenv
def test_env_file_named_by_bloggen_env_is_read(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    other = tmp_path / "shared.env"
    other.write_text(f'GEMINI_API_KEY=x\nexport {outdir.VAR}="{tmp_path}/out"\n')
    monkeypatch.setenv("BLOGGEN_ENV", str(other))
    assert outdir.blogpost_dir(str(tmp_path / "tool")) == str(tmp_path / "out")


@needs_dotenv
def test_env_file_is_found_in_a_parent_folder(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    (tmp_path / ".env").write_text(f"{outdir.VAR}={tmp_path}/shared\n")
    tool = tmp_path / "group" / "tool"
    tool.mkdir(parents=True)
    assert outdir.blogpost_dir(str(tool)) == str(tmp_path / "shared")


@needs_dotenv
def test_quotes_and_inline_comments_are_dropped(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    env = tmp_path / ".env"
    env.write_text(f"{outdir.VAR}=/data/posts  # my posts\n")
    assert outdir.blogpost_dir(str(tmp_path)) == "/data/posts"
    env.write_text(f'{outdir.VAR}="/data/my posts" # c\n')
    assert outdir.blogpost_dir(str(tmp_path)) == "/data/my posts"


def test_without_dotenv_the_file_is_not_read_and_a_note_says_so(tmp_path, monkeypatch, capsys):
    _no_env(monkeypatch)
    monkeypatch.setitem(sys.modules, "dotenv", None)
    (tmp_path / ".env").write_text(f"{outdir.VAR}=/data/posts\n")
    assert outdir.blogpost_dir(str(tmp_path)) == str(tmp_path / "blogposts")
    assert "python-dotenv is not installed" in capsys.readouterr().err


def test_without_dotenv_a_file_that_does_not_set_the_variable_prints_nothing(tmp_path, monkeypatch, capsys):
    _no_env(monkeypatch)
    monkeypatch.setitem(sys.modules, "dotenv", None)
    (tmp_path / ".env").write_text("GEMINI_API_KEY=x\n")
    assert outdir.blogpost_dir(str(tmp_path)) == str(tmp_path / "blogposts")
    assert capsys.readouterr().err == ""
