"""XAMS simulation app (plan S10): which simulations exist and how they were made; later the composer.

    xamssim web [--host 127.0.0.1] [--port 8071]

Read-only (phase a): everything comes from xamssim.compose (the data folder of this machine: $XAMSSIM_DATA, the run
files under $XAMSSIM_STUDIES); the only files written are the figure PNGs next to the provenance records.
"""
from __future__ import annotations

import os

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

from xamssim import compose

app = Flask(__name__, template_folder="templates", static_folder="static")
DASHBOARD = os.environ.get("XAMSSIM_DASHBOARD_URL", "")          # link to the xams-dashboard, if known


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    if isinstance(v, (list, tuple)) and len(v) <= 8:
        return ", ".join(_fmt(x) for x in v)
    return "" if v is None else str(v)


app.jinja_env.filters["fmt"] = _fmt


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
    return render_template("simulation.html", run_id=run_id, d=d, figures=compose.FIGURES, others=others,
                           optical=optical, map_figures=compose.MAP_FIGURES, dashboard=DASHBOARD, page="overview")


@app.route("/sim/<run_id>/figure/<name>.png")
def figure(run_id, name):
    if name not in compose.FIGURES:
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
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
