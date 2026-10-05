"""Note: XAMS optical simulation — model, validation, results, comparison with the data, design study.
Figures and numbers from results/ (tools/step6_results.py, step7_compare.py, design_ptfe.py) and results/geometry.
Usage (from optical_sim/): python notes/make_note.py notes/XAMS_optical_simulation_2026-10-05.pdf"""
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FD = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("Arial", FD + "Arial.ttf")); pdfmetrics.registerFont(TTFont("Arial-Bold", FD + "Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", FD + "Arial Italic.ttf"))
registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-Bold")
NAVY, LIGHT, GREEN, AMBER, GRID = (colors.HexColor(c) for c in ("#1F3A5F", "#E8EEF5", "#E3F2E1", "#FFF4D6", "#9AA8B8"))
ss = getSampleStyleSheet()
base = ParagraphStyle("b", parent=ss["Normal"], fontName="Arial", fontSize=9.3, leading=12.3)
small = ParagraphStyle("s", parent=base, fontSize=7.8, leading=9.8)
cap = ParagraphStyle("c", parent=small, textColor=colors.HexColor("#4A5A6A"), spaceAfter=6)
h1 = ParagraphStyle("h1", parent=base, fontName="Arial-Bold", fontSize=17, leading=21, textColor=NAVY)
sub = ParagraphStyle("sub", parent=base, fontSize=9.5, textColor=colors.HexColor("#4A5A6A"), spaceAfter=5)
h2 = ParagraphStyle("h2", parent=base, fontName="Arial-Bold", fontSize=11.5, leading=14.5, textColor=NAVY, spaceBefore=8, spaceAfter=3)
hdr = ParagraphStyle("hdr", parent=small, fontName="Arial-Bold", textColor=colors.white)
W = A4[0] - 30 * mm
ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def P(t, st=base):
    return Paragraph(t, st)


def box(flow, bg):
    t = Table([[flow]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("BOX", (0, 0), (-1, -1), 0.6, GRID),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def table(data, widths):
    d = [[Paragraph(str(c), hdr if i == 0 else small) for c in r] for i, r in enumerate(data)]
    t = Table(d, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, GRID), ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")] +
                          [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(data), 2)]))
    return t


def img(path, width, caption):
    iw, ih = ImageReader(str(path)).getSize()
    return KeepTogether([Image(str(path), width=width, height=width * ih / iw), P(caption, cap)])


def cell(path, width, caption):
    """image + caption for a table cell (no KeepTogether inside tables)"""
    iw, ih = ImageReader(str(path)).getSize()
    return [Image(str(path), width=width, height=width * ih / iw), P(caption, cap)]


def bullets(items):
    return [P("• " + t) for t in items]


s6 = json.load(open(RES / "step6" / "summary.json"))
dp = json.load(open(RES / "design_ptfe" / "summary.json"))
l2, l1 = s6["losses_s2"], s6["losses_s1"]


def pc(x):
    return "&lt; 0.1 %" if 0 < x < 0.0005 else f"{100 * x:.1f} %"


def bars(L, m):
    return pc(L.get(f"mesh foil: {m}", 0))


def main(out):
    st = []
    st += [P("XAMS optical simulation: model, validation and first results", h1),
           P("Geant4 optical simulation of the XAMS TPC with the meshes as built — geometry v3 from the drawings · "
             "5 October 2026 · optical_sim/ (local git), user guide: optical_sim/docs (MkDocs)", sub)]
    st.append(box([P("<b>Summary.</b>"), *bullets([
        "Question: is the low S2 light on the top PMT a geometric effect? <b>Partly.</b> Geometry and optics give an S2 top "
        "fraction of 0.53–0.58 over all plausible optical parameters and liquid levels. The data without a source come "
        "close (0.50–0.68 depending on S2 size, 0.55 at 10–20 kPE); the Cs-137 and Na-22 values (0.27–0.40) are far below "
        "anything geometric — they are the load effect of the top PMT, not geometry.",
        "<b>The geometry is right:</b> the top-sector light pattern versus position (asymmetries u, v) lies inside the "
        "narrow simulation band over ±24 mm, identically for every source.",
        "<b>Fit:</b> the shapes of S2 versus r, S1 versus depth and the sector pattern are reproduced with two efficiency "
        "factors on the top/bottom ratio, ε<sub>S2</sub> = 1.13 and ε<sub>S1</sub> = 0.77 (QE ratio; top-PMT small-signal loss). Low "
        "steel reflectivity is preferred; PTFE reflectivity and Rayleigh length are not constrained.",
        "The S2 area fraction top in the data dips at the centre (r &lt; 5 mm); the model does not, and an insensitive cross "
        "between the top-PMT anodes cannot produce it (tested up to 6 mm).",
        "Only ~23 % of the S2 photons reach a photocathode (QE 0.33 → 7.6 % detected); the mesh foils take ~35 %, ~32 % go "
        "sideways into the rings or out of the model. The liquid level (2 → 4 mm) hardly matters.",
        "Design study: PTFE cylinders also in the gate–anode and anode–top-screen gaps raise the S2 light collection by "
        f"+{100 * (dp['s2'][4]['total'] / dp['s2'][0]['total'] - 1):.0f} %, with the cathode–bottom-screen gap "
        f"+{100 * (dp['s2'][5]['total'] / dp['s2'][0]['total'] - 1):.0f} % (S1 "
        f"+{100 * (dp['s1'][5]['total'] / dp['s1'][0]['total'] - 1):.0f} %) — a factor ~1.4, not more.",
    ])], GREEN))

    st += [P("1. Model", h2), P(
        "One event = one 178 nm photon, started uniformly in the source volume with a random direction and polarisation "
        "and followed until it is detected or lost (G4OpticalPhysics: absorption, Rayleigh scattering, boundaries; no "
        "scintillation). S2: liquid surface to just below the anode foil, r &lt; 30 mm; S1: cathode to gate, r &lt; 30 mm. "
        "Every photon is recorded (origin, end point, how it ended, sensor, reflections); maps are made by binning the origins.")]
    st.append(table([
        ["part", "model (geometry v2, from the drawings)"],
        ["meshes (5)", "solid 0.15 mm steel foils (Ø80) with 456 square holes 2.45 mm (pitch 2.6 mm) etched in a staircase-shaped "
                       "area (gate drawing; outer hole corners at r = 32.8 mm), the rest solid; all at 29.4° to the anodes. "
                       "z: top screen +18, anode +8, gate 0, cathode −51.8, bottom screen −59.6 mm"],
        ["mesh rings", "steel, Ø72–92.6 mm, 1.8 mm assembly; the foil (Ø80) on one face, the ring body on the other side: "
                       "below the gate and bottom screen, above the cathode, anode and top screen. The gate–anode gap is "
                       "therefore open sideways between r = 36 and 46 mm"],
        ["PTFE cylinder", "Ø62/72 mm, 50.85 mm, in the bores of the gate and cathode rings (0.8 mm gap to the cathode foil); "
                          "R 0.90–0.99, specular fraction 0–0.2, rest Lambertian"],
        ["copper rings", "four field-shaping rings Ø72–92.6 × 1.8 mm around the PTFE (8 mm gaps), R 0.2–0.4"],
        ["xenon", "liquid n = 1.69 up to the level (2 / 3 / 4 mm above the gate), Rayleigh 30–60 cm, absorption 1–10 m; "
                  "gas n = 1.00 above"],
        ["PMTs", "two R12699: silica window 54.6 mm square, 2.5 mm, n = 1.60; photocathode 48.5 mm square with QE 0.33 "
                 "(top: 4 sectors = ch1–ch4); frame and body absorbing"],
        ["SiPMs", "two, on the PTFE inner wall at z = −25 mm, azimuth 0° / 90°"],
        ["outside", "everything beyond |x|, |y| = 60 mm, below −90 or above +45 mm absorbs (to be made realistic)"],
    ], [28 * mm, W - 28 * mm]))
    st.append(Spacer(1, 4))
    st.append(Table([[cell(RES / "geometry" / "section_xz.png", W * 0.52,
                           "Cross section at y = 0 from Geant4's own navigator (exactly what the simulation uses)."),
                      cell(RES / "geometry" / "view_cut.png", W * 0.43,
                           "3-D view, cut open: PTFE (cream), mesh rings (grey), copper rings, PMTs.")]],
                    colWidths=[W * 0.54, W * 0.46]))

    st += [P("2. Validation", h2), P("Each implementation step ended with a check against an analytic result:")]
    st.append(table([
        ["check", "result"],
        ["solid angle (point source, 48.5 mm cathode at 10/30/60 mm)", "detected fraction = solid angle, pulls ≤ 1.1"],
        ["Fresnel + total internal reflection at the liquid surface, 0–80°", "matches (Rs+Rp)/2; TIR from the critical angle 36.3°"],
        ["mesh transparency, θ 0–75°, φ 0/29.4/45°", "Geant4 = analytic ray trace photon by photon (3·10<super>6</super> photons); "
                                                      "0.888 at normal incidence"],
        ["optical surfaces (PTFE, steel)", "reflected fraction = R, specular share = f, diffuse part Lambertian; R = 1 closes"],
        ["sources and bookkeeping", "z ranges follow the liquid level; every photon counted once"],
        ["seed / statistics", "independent halves of every scan point agree (worst pull 2.3)"],
    ], [70 * mm, W - 70 * mm]))

    st += [PageBreak(), P("3. Results", h2), P("<b>S2 top fraction.</b> Over the full ranges of the free parameters and "
           "liquid levels: 0.531–0.584. Strongest knobs: PTFE specular fraction (−0.034 from 0 to 0.2), steel and PTFE "
           "reflectivity (≈ −0.02 each over their ranges), Rayleigh length (−0.014); liquid level 2 → 4 mm only +0.010. "
           "Versus radius 0.62 at the centre → 0.52 at the edge.")]
    st.append(img(RES / "step6" / "s2_topfraction.png", W, "S2 top fraction vs PTFE reflectivity for three steel "
                  "reflectivities and three liquid levels (10<super>7</super> photons per point; statistical errors ±0.0006)."))
    st.append(P("<b>Where the light ends.</b> Reference point: level 4 mm, PTFE R 0.95, steel R 0.35, copper R 0.3."))
    st.append(table([
        ["", "S2", "S1"],
        ["detected top / bottom PMT (QE incl.)", f"{pc(l2['detected top PMT'])} / {pc(l2['detected bottom PMT'])}",
         f"{pc(l1['detected top PMT'])} / {pc(l1['detected bottom PMT'])}"],
        ["photocathode reached, not converted (1 − QE)", pc(l2["photocathode, not converted (1 - QE)"]),
         pc(l1["photocathode, not converted (1 - QE)"])],
        ["leaves the TPC region sideways", pc(l2["leaves the TPC region"]), pc(l1["leaves the TPC region"])],
        ["mesh rings + foil rims", pc(l2["mesh rings (+ foil rim)"]), pc(l1["mesh rings (+ foil rim)"])],
        ["mesh foils: anode / gate / top screen / cathode / bottom screen",
         " / ".join(bars(l2, m) for m in ("anode", "gate", "top_screen", "cathode", "bottom_screen")),
         " / ".join(bars(l1, m) for m in ("anode", "gate", "top_screen", "cathode", "bottom_screen"))],
        ["PTFE", pc(l2["PTFE"]), pc(l1["PTFE"])],
        ["PMT frame / body", pc(l2["PMT frame / body"]), pc(l1["PMT frame / body"])],
        ["copper field-shaping rings", pc(l2["copper field-shaping rings"]), pc(l1["copper field-shaping rings"])],
        ["absorbed in the liquid", pc(l2["bulk absorption (LXe)"]), pc(l1["bulk absorption (LXe)"])],
    ], [80 * mm, (W - 80 * mm) / 2, (W - 80 * mm) / 2]))
    st.append(Spacer(1, 4))
    st.append(img(RES / "step6" / "s1_vs_z.png", W * 0.98,
                  "S1: top fraction (0.11 at the cathode → 0.25–0.27 at the gate) and light collection vs depth."))
    st.append(img(RES / "step6" / "s2_sectors.png", W, "Share of each top-PMT sector in the top light versus S2 position "
                  "(simulation frame: sector I at −x+y, II +x+y, III −x−y, IV +x−y)."))

    st += [PageBreak(), P("4. Comparison with the data", h2), P(
        "Data: Δ750 V runs of 28/29-09 (central processing v4), no source / Na-22 / Cs-137, r &lt; 25 mm, area fractions "
        "with the LED gains only (the v2 load correction f_top undone). Simulation band: all optics points at the 4 mm "
        "level, equal QE top and bottom.")]
    st.append(img(RES / "step7" / "compare.png", W, "Data vs simulation: S2 area fraction top vs S2 size and vs r, S1 "
                  "vs z, and the top-sector asymmetries u(x), v(y)."))
    st += bullets([
        "<b>Sector pattern:</b> data inside the simulation band over ±24 mm, identical for all sources — geometry right.",
        "<b>S2 versus size and source:</b> no source 0.68 (3–5 kPE) → 0.49 (&gt; 100 kPE); Na-22 0.53 → 0.36; Cs-137 0.40 → "
        "0.27. Rate and size dependence are top-PMT effects (load, large pulses), not geometry. The simulation (0.55–0.60) "
        "agrees with the low-load, medium-size data.",
        "<b>S2 versus r:</b> outside the centre data/simulation top/bottom ratio 1.0–1.2; at r &lt; 5 mm 0.6–0.7 (central dip "
        "in every source).",
        "<b>S1 versus z:</b> same shape, constant ratio 0.72 (one efficiency factor for small signals on the top PMT).",
        "Implied top-PMT efficiency relative to geometry (S2): ≈ 1 without source, ≈ 0.3 for Cs-137 large S2 — the v2 gain "
        "factor f_top (0.74–0.88, anchored on Cs runs) corrects only part of it.",
    ])

    s8 = json.load(open(RES / "step8" / "summary.json"))
    b8 = s8["best"]
    st += [P("5. Fit of the optical parameters", h2), P(
        "81-point grid (PTFE reflectivity 0.90/0.95/0.99 × PTFE specular fraction 0/0.1/0.2 × steel reflectivity "
        "0.2/0.35/0.5 × Rayleigh length 30/45/60 cm) for S2 and S1, binned like the data. Per point two efficiency factors "
        "multiply the top/bottom ratio (ε<sub>S2</sub>, ε<sub>S1</sub>); the optical parameters are constrained by the shapes "
        "(S2 vs r for r ≥ 5 mm, S1 vs z, u/v), with a systematic floor on each observable.")]
    st.append(img(RES / "step8" / "best_fit.png", W, "Best grid point vs data (no source) and χ² profiles."))
    st += bullets([
        f"Best point: PTFE R {b8['PTFE R']}, specular {b8['PTFE specular']}, steel R {b8['steel R']}, Rayleigh "
        f"{b8['Rayleigh [cm]']} cm; χ² {b8['chi2_s2r']:.1f} / {b8['chi2_s1z']:.1f} / {b8['chi2_uv']:.1f} for 7 / 11 / 45 dof "
        "(S2 vs r / S1 vs z / u, v).",
        f"ε<sub>S2</sub> = {b8['eps_s2']:.2f} ({s8['eps_range_good']['s2'][0]:.2f}–{s8['eps_range_good']['s2'][1]:.2f}), "
        f"ε<sub>S1</sub> = {b8['eps_s1']:.2f} ({s8['eps_range_good']['s1'][0]:.2f}–{s8['eps_range_good']['s1'][1]:.2f}): not one "
        "QE ratio — with a QE ratio of ~1.1 the top PMT keeps only ~0.68 of its small S1 signals relative to the bottom, "
        "consistent with the known small-signal integration loss.",
        "Steel reflectivity low (0.2 preferred over 0.5, Δχ² 34) and a small specular PTFE part (0.1–0.2 over 0, Δχ² 35); "
        "PTFE reflectivity and Rayleigh length are not constrained.",
        "Dead cross on the top PMT (1.5 / 3 / 6 mm): centre / ring at most 1.03 → 1.00, data 0.79 — not the cause of the "
        "central dip.",
    ])

    st += [P("6. Design study: extra PTFE cylinders", h2), P(
        "PTFE cylinders with the radii of the drift-region PTFE, inside the ring bores, foil to foil:")]
    rows = [["extra PTFE", "S2 light", "S2 vs now", "S1 light", "S1 vs now", "S2 top fraction"]]
    for a, b in zip(dp["s2"], dp["s1"]):
        rows.append([a["config"], pc(a["total"]), f"{100 * (a['total'] / dp['s2'][0]['total'] - 1):+.0f} %", pc(b["total"]),
                     f"{100 * (b['total'] / dp['s1'][0]['total'] - 1):+.0f} %", f"{a['top_fraction']:.3f}"])
    st.append(table(rows, [62 * mm] + [(W - 62 * mm) / 5] * 5))
    st += [Spacer(1, 3), P("Most rescued photons still end on meshes, PMT frames or in the photocathode (QE), so the gain "
           "is a factor ~1.4. Not studied: high voltage (PTFE across 5 kV gate–anode, charge-up in the extraction region), "
           "mechanics.", small)]

    st += [P("7. Limitations and next steps", h2)]
    st.append(box(bullets([
        "Everything outside |x|, |y| &lt; 60 mm is black and the three gate–anode pillars are missing: ~22 % of the S2 light "
        "leaves the model sideways. The surrounding structure (holders, field-cage parts, cryostat wall) is next (TODO) — it "
        "affects light collection and the design study, little the top fraction.",
        "Central S2 dip: check the position reconstruction near u = v = 0 (AFT versus u, v directly), since the PMT cross is excluded.",
        "Optical parameters: a finer grid with more photons (u/v term) to constrain PTFE reflectivity and Rayleigh length; "
        "measure the top-PMT small-signal efficiency (amstrax integration) to separate it from the QE ratio.",
        "Oct 2024 (2 + 6 mm liquid/gas) vs now (4 + 4 mm): the simulation predicts only +0.01 in the S2 top fraction.",
    ]), AMBER))

    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=13 * mm, bottomMargin=13 * mm,
                            title="XAMS optical simulation", author="XAMS")
    doc.build(st)
    print("written", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "notes" / "XAMS_optical_simulation_2026-10-05.pdf"))
