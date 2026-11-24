"""web/view.py: the simulation app shows someone else's simulations read-only (a student, the private simulations of
a colleague): one folder fills the five paths, each can be changed; the environment switches, back to the own."""
import json
import os
import subprocess
import sys

import pytest

from xamssim.config import ROOT

sys.path.insert(0, str(ROOT))
from web import view  # noqa: E402


@pytest.fixture
def colleague(tmp_path, monkeypatch):
    root = tmp_path / "users" / "acolijn" / "xamssim"
    for sub in ("data", "simulations", "strax_data", "live_mc", "processed"):
        (root / sub).mkdir(parents=True)
    monkeypatch.setenv("XAMSSIM_WEB_VIEW_FILE", str(tmp_path / "home" / ".xams" / "sim_view.json"))
    monkeypatch.setenv("XAMSSIM_USER_ENV", str(tmp_path / "home" / "env"))
    monkeypatch.delenv("XAMSSIM_WEB_ACCESS", raising=False)
    return root


def test_folder_fills_five_paths(colleague):
    p = view.paths_for(str(colleague) + "/")
    assert p["XAMSSIM_DATA"] == f"{colleague}/data" and p["XAMSSIM_STUDIES"] == f"{colleague}/simulations"
    assert p["XAMSSIM_AMSTRAX_STORE"] == f"{colleague}/strax_data" and len(p) == 5
    assert view.check(p) == {}


def test_check(colleague, tmp_path):
    assert view.check({"XAMSSIM_DATA": "rel/path"})["XAMSSIM_DATA"] == "give an absolute path"
    bad = view.check({"XAMSSIM_DATA": str(colleague / "data"), "XAMSSIM_STUDIES": str(tmp_path / "nope"),
                      "XAMSSIM_LIVE": str(tmp_path / "not_yet")})                  # live may be missing
    assert list(bad) == ["XAMSSIM_STUDIES"]
    assert "needed" in view.check({"XAMSSIM_STUDIES": str(colleague / "simulations")})["XAMSSIM_DATA"]


def test_environment_switch_and_back(colleague, tmp_path):
    own = {"XAMSSIM_DATA": str(tmp_path / "mine" / "data"), "XAMSSIM_WEB_SUBMIT": "1", "HOME": "/h"}
    new = view.environment(own, view.paths_for(str(colleague)))
    assert new["XAMSSIM_DATA"] == f"{colleague}/data" and new["XAMSSIM_LIVE"] == f"{colleague}/live_mc"
    assert new["XAMSSIM_WEB_SUBMIT"] == "0" and new[view.VIEWING] == f"{colleague}/data" and new["HOME"] == "/h"
    assert view.environment(new, view.paths_for(str(colleague))) is None            # already showing it: no restart
    back = view.environment(new, {})
    assert back == own                                                             # own paths and rerun again


def test_own_data_folder_is_not_read_only(tmp_path):
    env = {"XAMSSIM_DATA": str(tmp_path / "data")}
    new = view.environment(env, {"XAMSSIM_DATA": str(tmp_path / "data"), "XAMSSIM_STUDIES": str(tmp_path / "s")})
    assert new["XAMSSIM_STUDIES"] == str(tmp_path / "s") and view.VIEWING not in new and "XAMSSIM_WEB_SUBMIT" not in new


def test_save_load_exports(colleague, monkeypatch):
    for k in view.PARTS:
        monkeypatch.delenv(k, raising=False)
    view.save(view.paths_for(str(colleague)))
    assert view.load()["XAMSSIM_STUDIES"] == f"{colleague}/simulations"
    out = view.exports()
    assert f"export XAMSSIM_DATA={colleague}/data" in out and "export XAMSSIM_WEB_SUBMIT=0" in out
    monkeypatch.setenv("XAMSSIM_WEB_ACCESS", "central")                            # never on the central app
    assert view.exports() == "" and not view.allowed()


def test_exports_with_plain_python(colleague, tmp_path):
    """The start script runs it with the system python3, before any setup: standard library only."""
    view.save(view.paths_for(str(colleague)))
    env = {k: v for k, v in os.environ.items() if not k.startswith("XAMSSIM_") or k in ("XAMSSIM_WEB_VIEW_FILE",)}
    env["PYTHONPATH"] = ""
    r = subprocess.run([sys.executable, "-S", "-m", "web.view", "exports"], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0 and f"XAMSSIM_DATA={colleague}/data" in r.stdout, r.stderr


def test_unreadable_setting_ignored(colleague, tmp_path, monkeypatch):
    view.save({"XAMSSIM_DATA": str(tmp_path / "gone")})
    monkeypatch.setenv("XAMSSIM_DATA", str(tmp_path / "mine"))
    assert view.exports() == ""


def test_rerun_refused_while_viewing(monkeypatch):
    from xamssim import compose
    monkeypatch.setattr(compose, "rerun_plan", lambda run_id: {"dst": "/x.yaml"})
    monkeypatch.setenv("XAMSSIM_WEB_VIEWING", "/somebody/data")
    monkeypatch.setenv("XAMSSIM_WEB_SUBMIT", "1")
    with pytest.raises(PermissionError, match="read-only"):
        compose.rerun("990089")


def test_figure_file_falls_back_when_not_writable(tmp_path, monkeypatch):
    from xamssim import compose
    ro = tmp_path / "ro"
    (ro / "figures").mkdir(parents=True)
    out = ro / "figures" / "a.png"
    assert compose._figure_file(out) == out
    monkeypatch.setattr(compose.os, "access", lambda p, m: False)
    alt = compose._figure_file(out)
    assert alt != out and alt.name.endswith("_a.png") and str(alt).startswith(compose.tempfile.gettempdir())


def test_settings_page(colleague, monkeypatch):
    from web import app as A
    monkeypatch.setattr(A.view, "restart", lambda env, delay=0: setattr(A, "_restarted", env))
    c = A.app.test_client()
    assert c.get("/settings").status_code == 200
    r = c.post("/settings", data={"folder": str(colleague), "fill": "1"})
    assert f"{colleague}/simulations".encode() in r.data                           # filled in, not saved
    assert view.load() == {}
    r = c.post("/settings", data=view.paths_for(str(colleague)))
    assert b"restarts" in r.data and view.load()["XAMSSIM_DATA"] == f"{colleague}/data"
    assert A._restarted["XAMSSIM_WEB_SUBMIT"] == "0"
