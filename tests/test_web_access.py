"""web/access.py: the private app needs the token on every request; the central one needs a key of a user with
central_actions for actions; open on your own machine."""
import importlib
import json
import os
import sys

import pytest

from xamssim.config import ROOT

sys.path.insert(0, str(ROOT))
TOKEN = "t" * 32
KEY = "k" * 32


@pytest.fixture
def files(tmp_path, monkeypatch):
    s = tmp_path / "private.json"
    s.write_text(json.dumps({"token": TOKEN, "strax_folder": "/x"}))
    k = tmp_path / "keys.json"
    k.write_text(json.dumps({"users": {"acolijn": KEY, "student": "s" * 32}}))
    os.chmod(k, 0o600)
    u = tmp_path / "users.yaml"
    u.write_text("users:\n  acolijn: {account: z37, sim_port: 8077, central_actions: true}\n"
                 "  student: {account: s99, sim_port: 21301}\n")
    monkeypatch.setenv("XAMS_PRIVATE_SETTINGS", str(s))
    monkeypatch.setenv("XAMS_DASH_KEYS_FILE", str(k))
    monkeypatch.setenv("XAMS_DASH_USERS_FILE", str(u))
    return s, k, u


def _app(monkeypatch, mode):
    from flask import Flask, g
    from web import access
    monkeypatch.setenv("XAMSSIM_WEB_ACCESS", mode)
    app = Flask("t")
    access.install(app)
    app.add_url_rule("/", "i", lambda: "act" if g.can_act else "view")
    app.add_url_rule("/do", "do", lambda: "done", methods=["POST"])
    return app.test_client()


def test_private_needs_token(files, monkeypatch):
    c = _app(monkeypatch, "private")
    assert c.get("/").status_code == 403 and c.get("/?token=wrong").status_code == 403
    r = c.get("/?token=" + TOKEN)
    assert r.status_code == 302 and "token" not in r.headers["Location"]
    assert c.get("/").get_data(as_text=True) == "act"                       # cookie from now on
    assert c.post("/do").status_code == 200


def test_private_cookie_of_the_dashboard_works(files, monkeypatch):
    c = _app(monkeypatch, "private")
    c.set_cookie("xams_private_token", TOKEN)
    assert c.get("/").status_code == 200


def test_private_without_token_refuses(files, monkeypatch):
    files[0].write_text(json.dumps({"strax_folder": "/x"}))
    c = _app(monkeypatch, "private")
    assert c.get("/?token=").status_code == 403 and c.get("/", headers={"X-Token": ""}).status_code == 403


def test_central_view_open_actions_need_rights(files, monkeypatch):
    c = _app(monkeypatch, "central")
    assert c.get("/").get_data(as_text=True) == "view"
    assert c.post("/do").status_code == 403
    assert c.post("/do", headers={"X-Key": "s" * 32}).status_code == 403   # a key, but no central_actions
    assert c.post("/do", headers={"X-Key": KEY}).status_code == 200
    c.set_cookie("xams_dash_key", KEY)                                      # the central dashboard's cookie
    assert c.get("/").get_data(as_text=True) == "act"


def test_central_keys_readable_by_others_not_trusted(files, monkeypatch):
    os.chmod(files[1], 0o644)
    c = _app(monkeypatch, "central")
    assert c.post("/do", headers={"X-Key": KEY}).status_code == 403


def test_open_mode(monkeypatch):
    c = _app(monkeypatch, "")
    assert c.get("/").get_data(as_text=True) == "act" and c.post("/do").status_code == 200


def test_private_port(files, monkeypatch):
    from web import access
    assert access.private_port("s99") == 21301 and access.private_port("nobody") == 8077
    files[0].write_text(json.dumps({"token": TOKEN, "sim_port": 21999}))
    assert access.private_port("s99") == 21999                             # the settings first
