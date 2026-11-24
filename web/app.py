"""XAMS simulation app (plan S11): which simulations exist and how they were made; later the composer.

    xamssim web [--host 127.0.0.1] [--port 8071]

Read-only (phase a): everything comes from xamssim.compose (the data folder of this machine: $XAMSSIM_DATA, the run
files under $XAMSSIM_STUDIES); the only files written are the figure PNGs next to the provenance records.
"""
from __future__ import annotations

import os

from flask import Flask, abort, g, redirect, render_template, request, send_file, url_for

from xamssim import compose

app = Flask(__name__, template_folder="templates", static_folder="static")
from web import access, view  # noqa: E402

access.install(app)                  # token (private) / key for actions (central) on a shared host: web/access.py
# The reconstruction of an MC run is shown in Processing (xams-dashboard run page), opened through the XAMS launcher,
# which knows the tunnels and passes the key (central) or token (private runs).
LAUNCHER = os.environ.get("XAMSSIM_LAUNCHER_URL", "http://127.0.0.1:8090").rstrip("/")


@app.template_global()
def processing_url(number) -> str:
    from xamssim.runid import PRIVATE
    n = int(number)
    if PRIVATE[0] <= n <= PRIVATE[1]:
        return f"{LAUNCHER}/open/dashprivate?to=/run/{n}"
    return f"{LAUNCHER}/open/dashboard?to=/v3/run/{n}"


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, (list, tuple)) and len(v) <= 8:
        return ", ".join(_fmt(x) for x in v)
    return "" if v is None else str(v)


app.jinja_env.filters["fmt"] = _fmt


@app.context_processor
def _showing():
    return {"showing": view.showing()}


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Whose simulations the app shows: your own or (read-only) someone else's (web/view.py). The folder fills the
    five paths; each can be changed by hand."""
    if not view.allowed():
        abort(404)
    paths, bad = view.load(), {}
    if request.method == "POST":                     # private app: web/access.py has checked the token already
        f = request.form
        if f.get("own"):
            paths = {}
            own = view._own(dict(os.environ)).get("XAMSSIM_DATA")
            if not own and not view.own_settings():
                bad = {"XAMSSIM_DATA": "you have no simulations of your own (no XAMSSIM_DATA in ~/.config/xamssim/env)"}
                return render_template("settings.html", paths=view.load(), folder="", bad=bad, parts=view.PARTS,
                                       candidates=view.candidates(), switching=False, page="settings")
        elif f.get("fill"):                          # the folder button: fill the five fields, save nothing yet
            paths = view.paths_for((f.get("folder") or "").strip())
            return render_template("settings.html", paths=paths, folder=f.get("folder", ""), bad=view.check(paths),
                                   parts=view.PARTS, candidates=view.candidates(), switching=False, page="settings")
        else:
            paths = {k: (f.get(k) or "").strip().rstrip("/") for k in view.PARTS}
            paths = {k: v for k, v in paths.items() if v}
        bad = view.check(paths)
        if not bad:
            view.save(paths)
            new = view.environment(dict(os.environ), paths)
            if new is not None:
                view.restart(new, delay=0.5)         # after this answer: the app comes back with the other paths
                return render_template("settings.html", paths=paths, folder="", bad={}, parts=view.PARTS,
                                       candidates=[], switching=True, page="settings")
            return redirect(url_for("overview"))
    shown = paths or {k: v for k, v in view.showing()["paths"].items() if v}
    return render_template("settings.html", paths=shown, folder="", bad=bad, parts=view.PARTS,
                           candidates=view.candidates(), switching=False, page="settings")


@app.route("/")
def overview():
    d = compose.simulations()
    q = {k: request.args.get(k, "") for k in ("study", "state", "source", "status")}
    rows = [r for r in d["rows"] if all(not v or r.get(k) == v for k, v in q.items())]
    choices = {k: sorted({r.get(k) for r in d["rows"] if r.get(k)}) for k in q}
    return render_template("overview.html", d=d, rows=rows, q=q, choices=choices, page="overview")


@app.route("/sim/<run_id>")
def simulation(run_id):
    d = compose.detail(run_id)
    if d is None:
        abort(404)
    others = [r["id"] for r in compose.simulations()["rows"] if r["id"] != run_id]
    # The optical maps of this simulation: the key in its provenance record.
    key = ((d.get("record") or {}).get("maps") or {}).get("s1_light", {}).get("key")
    optical = compose.optical_map(key) if key else None
    rec = d.get("record")
    number = (d.get("row") or {}).get("number")
    reasons = compose.outdated_reasons(rec) if rec and (d.get("row") or {}).get("status") == "outdated" else []
    return render_template("simulation.html", run_id=run_id, d=d, figures=compose.FIGURES, figure_rows=compose.FIGURE_ROWS, others=others,
                           optical=optical, map_figures=compose.MAP_FIGURES, results=compose.RESULT_FIGURES,
                           daq=compose.daq_settings(rec) if rec else None, live=compose.live_settings(rec, number),
                           reasons=reasons, page="overview")


@app.route("/sim/<run_id>/reconstruction/<ev_hash>.png")
def reconstruction_figure(run_id, ev_hash):
    number = (compose.detail(run_id) or {}).get("row", {}).get("number")
    try:
        return send_file(compose.reconstruction_figure(run_id, number, ev_hash), mimetype="image/png")
    except (FileNotFoundError, TypeError):
        abort(404)


@app.route("/sim/<run_id>/rerun", methods=["GET", "POST"])
def rerun(run_id):
    """GET: what a rerun would do (new number, new run file, reasons); POST: write the run file and submit it."""
    result, error = None, ""
    try:
        plan = compose.rerun_plan(run_id)
    except (FileNotFoundError, ValueError) as e:
        return render_template("rerun.html", run_id=run_id, plan=None, result=None, error=str(e), page="overview")
    if request.method == "POST":                     # web/access.py has refused it already without the rights
        try:
            result = compose.rerun(run_id)
        except (PermissionError, FileExistsError, OSError) as e:
            error = str(e)
    return render_template("rerun.html", run_id=run_id, plan=plan, result=result, error=error,
                           can_submit=os.environ.get("XAMSSIM_WEB_SUBMIT") == "1" and g.get("can_act", False),
                           page="overview")


@app.route("/sim/<run_id>/figure/<name>.png")
def figure(run_id, name):
    if name not in compose.FIGURES and name not in compose.RESULT_FIGURES:
        abort(404)
    try:
        return send_file(compose.figure(run_id, name), mimetype="image/png")
    except FileNotFoundError:
        abort(404)


@app.route("/compare")
def compare():
    ids = [r["id"] for r in compose.simulations()["rows"]]
    a, b = request.args.get("a", ""), request.args.get("b", "")
    rows, error = [], ""
    if a and b:
        try:
            rows = compose.compare(a, b)
        except FileNotFoundError as e:
            error = str(e)
    return render_template("compare.html", ids=ids, a=a, b=b, rows=rows, error=error, page="compare")


@app.route("/maps")
def maps():
    return render_template("maps.html", m=compose.simulations()["maps"], optical=compose.optical_maps(), page="maps")


@app.route("/maps/optical/<key>")
def optical_map(key):
    o = compose.optical_map(key)
    if o is None:
        abort(404)
    return render_template("optical.html", o=o, figures=compose.MAP_FIGURES, page="maps")


@app.route("/maps/<kind>/<key>/figure.png")
def map_figure(kind, key):
    try:
        return send_file(compose.map_figure(kind, key), mimetype="image/png")
    except FileNotFoundError:
        abort(404)


@app.route("/reload")
def reload():
    compose._CACHE.clear()
    return redirect(request.referrer or url_for("overview"))


def main(host: str = "127.0.0.1", port: int = 8071, debug: bool = False):
    compose.warm()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
