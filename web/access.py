"""Who may use the simulation app on a shared host (stbc-i1): anyone logged in there can reach 127.0.0.1.

XAMSSIM_WEB_ACCESS (set by web/start_stbc.sh):

    private   the user's own app: every request needs the user's token, the "token" of ~/.xams/private.json
              (XAMS_PRIVATE_SETTINGS), the same token as the private processing dashboard: ?token=... once, then the
              cookie xams_private_token (shared with the private dashboard: both are on 127.0.0.1), or X-Token
    central   the production app (xamsdata): reading is open; actions (rerun = condor jobs as xamsdata) need a key of
              the xams-dashboard keys file (~/.xams_dashboard_keys.json, mode 600) of a user with central_actions in
              users.yaml (XAMS_DASH_USERS_FILE, default ~/xams-dashboard/users.yaml): ?key=... once, then the cookie
              xams_dash_key (the one the central dashboard sets), or X-Key
    (unset)   open: the app on your own machine

Fail closed: no token, no keys file, a keys file readable by others or no users file means no access / no actions.

    python -m web.access port     the port of the private app: sim_port of the settings, else users.yaml, else 8077
"""
from __future__ import annotations

import getpass
import hmac
import json
import os
from pathlib import Path

TOKEN_COOKIE = "xams_private_token"
KEY_COOKIE = "xams_dash_key"


def mode() -> str:
    return os.environ.get("XAMSSIM_WEB_ACCESS", "").strip().lower()


def _settings() -> dict:
    p = Path(os.environ.get("XAMS_PRIVATE_SETTINGS") or Path.home() / ".xams" / "private.json")
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def token() -> str:
    t = str(_settings().get("token") or "")
    return t if len(t) >= 20 else ""


def _keys() -> dict:
    p = Path(os.environ.get("XAMS_DASH_KEYS_FILE") or Path.home() / ".xams_dashboard_keys.json")
    try:
        if p.stat().st_mode & 0o077:
            return {}
        users = json.loads(p.read_text()).get("users") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    return {str(k): str(v) for k, v in users.items() if v and len(str(v)) >= 20}


def _users() -> dict:
    p = Path(os.environ.get("XAMS_DASH_USERS_FILE") or Path.home() / "xams-dashboard" / "users.yaml")
    try:
        import yaml
        return (yaml.safe_load(p.read_text()) or {}).get("users") or {}
    except Exception:                                                # noqa: BLE001  (no file / bad file: no users)
        return {}


def token_ok(value) -> bool:
    t = token()
    return bool(t) and bool(value) and hmac.compare_digest(str(value), t)


def key_user(value) -> str | None:
    if not value:
        return None
    for name, key in _keys().items():
        if hmac.compare_digest(str(value), key):
            return name
    return None


def may_act(key_value) -> bool:
    """Central: the key belongs to a user with central_actions: true."""
    name = key_user(key_value)
    return bool(name) and (_users().get(name) or {}).get("central_actions") is True


def _port(v):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    return v if 1024 < v < 65536 else None


def private_port(account: str | None = None) -> int:
    p = _port(_settings().get("sim_port"))
    if p:
        return p
    account = account or getpass.getuser()
    for name, d in _users().items():
        d = d or {}
        if str(d.get("account") or name) == account and _port(d.get("sim_port")):
            return _port(d.get("sim_port"))
    return 8077


def install(app):
    """The checks of mode() on every request of the Flask app."""
    from urllib.parse import urlencode

    from flask import abort, g, make_response, redirect, request

    import logging
    import re

    class _Hide(logging.Filter):                                     # the request log must not show secrets
        def filter(self, record):
            hide = lambda x: re.sub(r"(token|key)=[^\s&\"]+", r"\1=***", x)   # noqa: E731
            record.msg = hide(str(record.msg))
            if record.args:
                record.args = tuple(hide(a) if isinstance(a, str) else a for a in record.args)
            return True
    logging.getLogger("werkzeug").addFilter(_Hide())

    m = mode()
    if not m:
        @app.before_request
        def _open():
            g.can_act = True
        return

    @app.before_request
    def _check():
        if m == "private":
            if not token():
                abort(make_response("no token in ~/.xams/private.json: start the private processing dashboard once "
                                    "(xams-dashboard ops/start_private.sh) or run xams-web.sh setup", 403))
            if not (token_ok(request.args.get("token")) or token_ok(request.cookies.get(TOKEN_COOKIE))
                    or token_ok(request.headers.get("X-Token"))):
                abort(make_response("forbidden: open your private simulation app through the launcher", 403))
            g.can_act = True
            arg = "token"
        else:                                                        # central
            key = request.args.get("key") or request.cookies.get(KEY_COOKIE) or request.headers.get("X-Key")
            g.can_act = may_act(key)
            if request.method not in ("GET", "HEAD", "OPTIONS") and not g.can_act:
                abort(make_response("forbidden: actions on the central simulation app need the key of a user with "
                                    "central_actions (open it through the launcher)", 403))
            arg = "key"
        v = request.args.get(arg)
        if request.method == "GET" and v:                            # cookie, then the address without the secret
            args = {k: x for k, x in request.args.items() if k != arg}
            resp = make_response(redirect(request.path + ("?" + urlencode(args) if args else ""), code=302))
            ok = token_ok(v) if arg == "token" else bool(key_user(v))
            if ok:
                resp.set_cookie(TOKEN_COOKIE if arg == "token" else KEY_COOKIE, v, httponly=True, samesite="Strict",
                                max_age=30 * 24 * 3600)
            resp.headers["Referrer-Policy"] = "no-referrer"
            return resp
        return None


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["port"]:
        print(private_port())
    else:
        print(__doc__)
        sys.exit(1)
