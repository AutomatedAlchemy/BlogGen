"""Regression tests for the parent->child screenshot-path handoff.

This tool runs as two processes: the parent takes the screenshot and writes it
to a per-invocation ``tempfile.mkdtemp`` path, then spawns a *second* konsole
process (``main.py --analyze-only``) that reads it. Because the temp path is
created at module-import time, the child re-derives a DIFFERENT random dir
unless the parent explicitly passes its path down. These tests pin that the
parent communicates the exact path, so the child never looks in the wrong dir.

Hermetic + offline: heavy GUI/cloud imports are stubbed via sys.modules
injection before importing main.py under a repo-unique module name.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parent
MAIN_PY = TOOL_DIR / "main.py"


def _stub_modules():
    """Lightweight stand-ins for main.py's heavy/desktop-only imports."""
    stubs = {}

    google_pkg = types.ModuleType("google")
    google_pkg.__path__ = []  # mark as package
    genai = types.ModuleType("google.generativeai")
    genai.configure = lambda **k: None
    genai.GenerativeModel = lambda *a, **k: None
    gtypes = types.ModuleType("google.generativeai.types")
    gtypes.HarmCategory = types.SimpleNamespace()
    gtypes.HarmBlockThreshold = types.SimpleNamespace()
    genai.types = gtypes
    google_pkg.generativeai = genai
    stubs["google"] = google_pkg
    stubs["google.generativeai"] = genai
    stubs["google.generativeai.types"] = gtypes

    pil = types.ModuleType("PIL")
    pil.Image = types.SimpleNamespace(open=lambda *a, **k: None)
    stubs["PIL"] = pil

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *a, **k: None
    dotenv.find_dotenv = lambda *a, **k: ""
    stubs["dotenv"] = dotenv

    termcolor = types.ModuleType("termcolor")
    termcolor.colored = lambda text, *a, **k: text
    stubs["termcolor"] = termcolor

    shared_pkg = types.ModuleType("_shared")
    shared_pkg.__path__ = []
    shared_gui = types.ModuleType("_shared.gui")
    shared_gui.DataRetrievalWindow = object
    shared_gui.DataRetrievalConfig = object
    shared_inst = types.ModuleType("_shared.tool_installer")

    class _FakeInstaller:
        def __init__(self, *a, **k):
            pass

        def install(self):
            pass

        def remove(self):
            pass

    shared_inst.ToolInstaller = _FakeInstaller
    shared_inst.ToolMetadata = lambda *a, **k: object()
    stubs["_shared"] = shared_pkg
    stubs["_shared.gui"] = shared_gui
    stubs["_shared.tool_installer"] = shared_inst

    return stubs


@pytest.fixture
def main_mod(monkeypatch):
    for name, mod in _stub_modules().items():
        monkeypatch.setitem(sys.modules, name, mod)
    # Keep argv clean so the --advertise short-circuit doesn't fire on import.
    monkeypatch.setattr(sys, "argv", ["main.py"])
    spec = importlib.util.spec_from_file_location("sb_main_under_test", MAIN_PY)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "sb_main_under_test", mod)
    spec.loader.exec_module(mod)
    return mod


def test_launch_passes_screenshot_path_to_child(main_mod, monkeypatch):
    captured = {}

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return types.SimpleNamespace(pid=1234)

    monkeypatch.setattr(main_mod.subprocess, "Popen", fake_popen)

    main_mod.launch_terminal_process()

    cmd = captured["cmd"]
    assert "--analyze-only" in cmd
    # The crux: the child must be handed the parent's exact temp path. Without
    # this, the child's fresh mkdtemp() points elsewhere -> FileNotFoundError.
    assert main_mod.TEMP_FILENAME in cmd, (
        "child invocation was not told the parent's screenshot path; "
        "it will look in a different mkdtemp dir"
    )
    assert cmd[cmd.index(main_mod.TEMP_FILENAME) - 1] == "--screenshot-path"


def test_preferred_model_is_tried_first(main_mod):
    # The tool must lead with gemini-3.5-flash regardless of the shared .env
    # ordering; remaining models stay as fallbacks.
    assert main_mod.PREFERRED_MODEL == "gemini-3.5-flash"
    assert main_mod.GEMINI_CANDIDATE_MODELS[0] == "gemini-3.5-flash"
    assert main_mod.GEMINI_CANDIDATE_MODELS.count("gemini-3.5-flash") == 1


def test_parse_arguments_accepts_screenshot_path(main_mod, monkeypatch):
    monkeypatch.setattr(
        main_mod.sys,
        "argv",
        ["main.py", "--analyze-only", "--screenshot-path", "/tmp/foo/x.png"],
    )
    args = main_mod.parse_arguments()
    assert args.screenshot_path == "/tmp/foo/x.png"


# ---- Claude-skill (SKILL.md) registration --------------------------------

def test_skill_frontmatter_name_matches_dir(main_mod):
    # The on-disk skill dir, the SKILL.md frontmatter, and the advertised
    # skill_name must all agree, or the installer GUI can't pair install/uninstall.
    assert main_mod.SKILL_DIR.name == "screenshot-blogpost"
    assert main_mod.SKILL_MD_CONTENT.startswith("---\nname: screenshot-blogpost\n")


def test_skill_install_uninstall_roundtrip(main_mod, monkeypatch, tmp_path):
    skill_dir = tmp_path / "skills" / "screenshot-blogpost"
    skill_file = skill_dir / "SKILL.md"
    monkeypatch.setattr(main_mod, "SKILL_DIR", skill_dir)
    monkeypatch.setattr(main_mod, "SKILL_FILE", skill_file)

    assert not skill_file.exists()

    main_mod._install_skill()
    assert skill_file.read_text(encoding="utf-8") == main_mod.SKILL_MD_CONTENT

    # Idempotent: re-installing leaves identical content (and doesn't raise).
    main_mod._install_skill()
    assert skill_file.read_text(encoding="utf-8") == main_mod.SKILL_MD_CONTENT

    # Uninstall removes the file AND the now-empty skill dir.
    main_mod._uninstall_skill()
    assert not skill_file.exists()
    assert not skill_dir.exists()

    # Idempotent: a second uninstall is a no-op, not an error.
    main_mod._uninstall_skill()


def test_advertise_declares_skill_name():
    # --advertise short-circuits before heavy imports, so this is a real subprocess
    # round-trip (no stubbing). skill_name is what surfaces the Skill checkbox.
    import subprocess
    out = subprocess.check_output([sys.executable, str(MAIN_PY), "--advertise"], text=True)
    meta = json.loads(out)
    assert meta[0]["skill_name"] == "screenshot-blogpost"
