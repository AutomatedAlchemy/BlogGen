"""Tests for source provenance — the record of where a post's material came from.

The point of the feature is that a published post can be traced back to the
project it was made from, so these pin the two things that make that possible:
the label a post is grouped under, and the record surviving both as a sidecar
and as a stamp inside the HTML (the folder gets moved, the sidecar is lost, the
HTML alone must still say where it came from).

Hermetic: publish.py is stdlib-only, so it is imported directly and pointed at
a tmp_path output dir. No network, no browser, no Gemini.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

import provenance  # noqa: E402
import publish  # noqa: E402

POST_HTML = ('<!DOCTYPE html><html><head><meta charset="UTF-8">'
             "<title>A Post</title></head><body><p>Body.</p></body></html>")


@pytest.fixture
def repo(tmp_path):
    """A throwaway git repo to run a publish from."""
    root = tmp_path / "my-project"
    root.mkdir()
    env = {"GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "HOME": str(tmp_path),
           "PATH": "/usr/bin:/bin"}
    run = lambda *a: subprocess.run(("git", "-C", str(root)) + a, check=True,
                                    capture_output=True, env=env)
    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "T")
    (root / "seed.txt").write_text("seed\n")
    run("add", "seed.txt")
    run("commit", "-qm", "seed")
    return root


def test_label_prefers_the_repo_over_a_declared_file(repo):
    """A chip reading 'status.html' would be useless — group by project."""
    rec = provenance.collect("agent", sources=[".state/status.html"], cwd=str(repo))
    assert rec["label"] == "my-project"
    assert rec["repo"]["branch"] == "main"
    assert rec["repo"]["commit"]
    # the specific origin is kept, just not as the label
    assert rec["sources"] == [".state/status.html"]


def test_label_falls_back_to_declared_then_cwd(tmp_path):
    plain = tmp_path / "loose_dir"
    plain.mkdir()
    assert provenance.collect("agent", cwd=str(plain))["label"] == "loose_dir"
    rec = provenance.collect("agent", sources=["mujoco training"], cwd=str(plain))
    assert rec["label"] == "mujoco training"
    assert rec["repo"] is None


def test_inputs_are_absolute_and_deduped(tmp_path):
    rec = provenance.collect("agent", inputs=["a.png", "./a.png", "b.png", ""],
                             cwd=str(tmp_path))
    assert rec["inputs"] == [str(Path("a.png").resolve()), str(Path("b.png").resolve())]


def test_stamp_survives_without_the_sidecar():
    """The HTML alone must still carry the record if the folder is lost."""
    rec = provenance.collect("agent", sources=["topic"], cwd=".")
    stamped = provenance.stamp(POST_HTML, rec)
    assert provenance.read(html_text=stamped) == rec
    # stamping twice must not leave two tags behind
    twice = provenance.stamp(stamped, rec)
    assert twice.count("bloggen:provenance") == 1


def test_stamp_is_a_noop_without_a_head():
    assert provenance.stamp("<p>headless</p>", {"label": "x"}) == "<p>headless</p>"


def test_read_prefers_the_sidecar(tmp_path):
    provenance.write(str(tmp_path), {"label": "from-sidecar"})
    stamped = provenance.stamp(POST_HTML, {"label": "from-html"})
    assert provenance.read(str(tmp_path), stamped)["label"] == "from-sidecar"
    assert provenance.read(str(tmp_path / "nope"), stamped)["label"] == "from-html"


def test_publish_records_the_repo_it_was_run_from(tmp_path, repo, monkeypatch):
    out = tmp_path / "blogposts"
    out.mkdir()
    monkeypatch.setattr(publish, "BLOGPOST_DIR", str(out))
    monkeypatch.chdir(repo)

    src = tmp_path / "post.html"
    src.write_text(POST_HTML, encoding="utf-8")
    published = publish.publish(str(src), [], name="post", open_browser=False,
                                sources=[".state/status.html"])

    post_dir = Path(published).parent
    record = json.loads((post_dir / "source.json").read_text(encoding="utf-8"))
    assert record["label"] == "my-project"
    assert record["mode"] == "agent"
    assert record["cwd"] == str(repo)
    assert record["sources"] == [".state/status.html"]
    assert str(src) in record["inputs"]
    # and the same record is inside the published HTML
    assert provenance.read(html_text=Path(published).read_text(encoding="utf-8")) == record


def test_publish_without_provenance_flags_still_records_the_cwd(tmp_path, monkeypatch):
    out = tmp_path / "blogposts"
    out.mkdir()
    work = tmp_path / "somewhere"
    work.mkdir()
    monkeypatch.setattr(publish, "BLOGPOST_DIR", str(out))
    monkeypatch.chdir(work)

    src = tmp_path / "post.html"
    src.write_text(POST_HTML, encoding="utf-8")
    published = publish.publish(str(src), [], name="post", open_browser=False)

    record = json.loads((Path(published).parent / "source.json").read_text(encoding="utf-8"))
    assert record["label"] == "somewhere"
    assert record["sources"] == []
