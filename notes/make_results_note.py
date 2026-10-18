"""Results note: the optical simulation against a clean data set — selection, comparison, best optical parameters and
the relative top/bottom efficiencies, as currently understood. The full history (all intermediate steps) is in
make_note.py.
Usage (from optical_sim/, base conda python with reportlab):
    python notes/make_results_note.py notes/XAMS_optical_simulation_results_2026-10-11.pdf"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_note import (AMBER, GREEN, RES, ROOT, W, P, PageBreak, SimpleDocTemplate, Spacer, box, bullets, cap, h1,  # noqa: E402
                       h2, img, mm, small, sub, table, A4)

T_NONE = json.load(open(ROOT / "optical" / "targets" / "data_2026-10-11_clean.json"))
T_PP = json.load(open(ROOT / "optical" / "targets" / "data_2026-10-11_photopeak_clean.json"))
J = json.load(open(RES / "clean_joint" / "summary.json"))
FN = json.load(open(RES / "clean_fit_none" / "summary.json"))
FP = json.load(open(RES / "clean_fit_photopeak" / "summary.json"))
SW = json.load(open(RES / "s2width_map" / "summary.json"))


def cutflow_table():
    samples = [("no source", T_NONE["none"]["cutflow"]), ("Na-22", T_NONE["na22"]["cutflow"]),
               ("Cs-137", T_NONE["cs137"]["cutflow"]), ("Cs-137 photopeak", T_PP["cs137"]["cutflow"])]
    steps = [s for s, _ in samples[3][1]]
    rows = [["cut"] + [n for n, _ in samples]]
    for i, s in enumerate(steps):
        row = [s]
        for _, cf in samples:
            if i < len(cf):
                n0 = cf[1][1] if i >= 1 else cf[0][1]
                row.append(f"{cf[i][1]:,}" + (f" ({100 * cf[i][1] / n0:.0f} %)" if i >= 2 else ""))
            else:
                row.append("")
        rows.append(row)
    return table(rows, [70 * mm] + [(W - 70 * mm) / 4] * 4)


def main(out):
    b = J["best"]
    en, ep = J["none"], J["photopeak"]
    eps = J["eps_vs_size"]
    st = [P("XAMS optical simulation: results on a clean data set", h1),
          P("Geometry v4 · Δ750 V data of 28/29-09 (SR-2026.2, central processing v4, LED gains) · 11 October 2026 · "
            "the full history of the study is in XAMS_optical_simulation_2026-10-09.pdf", sub)]
    st.append(box([P("<b>Summary.</b>"), *bullets([
        "<b>Clean selection</b> (section 2): single scatters, S1 ≥ 20 PE in top and bottom, drift time &gt; 3 µs, S2 width "
        "at the gate &gt; 450 ns, S1 area fraction top consistent with the drift time. It removes 21–28 % of the single "
        "scatters and with them every population that disagreed with the model (central dip, near-gate events, mismatched "
        "S1/S2 pairs); energy spectrum and Cs-137 photopeak resolution are unchanged.",
        f"<b>The optics describes the clean data</b> (section 3): S2 area fraction top versus radius, S1 area fraction top "
        f"versus depth and the top-sector pattern, for no-source data and for Cs-137 photopeak events, with one set of "
        f"optical parameters. The central dip is gone (centre / ring {FN['data_centre_over_ring']:.2f}).",
        f"<b>Best optical parameters</b> (joint fit, section 4): PTFE reflectivity {b['PTFE R']}, PTFE specular fraction "
        f"{b['PTFE specular']}, steel reflectivity {b['steel R']}, Rayleigh length {b['Rayleigh [cm]']:.0f} cm "
        f"(χ² {J['chi2_joint']:.0f} / {J['ndf_joint']} dof). Steel reflectivity is well constrained (low); PTFE "
        "reflectivity 0.90–0.95, specular fraction 0.1–0.2 and Rayleigh length 45–60 cm are preferred.",
        "<b>Relative efficiency</b> ε (section 5): everything the simulation leaves out — the top/bottom QE and collection, "
        "the top-PMT gain drop under load, and a signal-size effect — multiplies the simulated top/bottom ratio. For large "
        f"signals ε depends only on the source rate: {eps['no source']['plateau']:.2f} without source, "
        f"{eps['Na-22']['plateau']:.2f} with Na-22, {eps['Cs-137']['plateau']:.2f} with Cs-137, the same for S1 and S2. "
        "Below 20 kPE ε rises with the same shape for every source (×1.3 at 10–20 kPE, ×2.2–2.8 at 3–5 kPE): not "
        "explained yet.",
    ])], GREEN))

    st += [P("1. What is compared", h2), P(
        "Geant4 optical simulation of the TPC (geometry v4 from the drawings: five etched meshes as built, PTFE drift "
        "cylinder, copper field-shaping rings, PTFE PMT holders, PTFE bucket and steel cryostat vessel; liquid level 4 mm "
        "above the gate). Photons start uniformly in the S2 region (liquid surface to anode, r &lt; 30 mm) or in the drift "
        "region (S1). Free optical parameters: PTFE reflectivity in liquid (0.90 / 0.95 / 0.99), its specular fraction "
        "(0 / 0.1 / 0.2), the steel reflectivity (0.2 / 0.35 / 0.5) and the Rayleigh scattering length (30 / 45 / 60 cm) — an "
        "81-point grid, 10<super>7</super> S2 and 2·10<super>7</super> S1 photons per point. The simulation uses equal QE "
        "(0.33) on both PMTs and records every photon; it knows nothing about gains, readout or the PMT load.")]
    st += bullets([
        "<b>S2 area fraction top versus r</b> (S2 3–20 kPE without source; all photopeak S2s): the shape of the S2 light "
        "split with position.",
        "<b>S1 area fraction top versus z</b>: the shape of the S1 light split with depth.",
        "<b>Top-sector asymmetries</b> u(x) = (ch1+ch3−ch2−ch4)/top along x and v(y) = (ch1+ch2−ch3−ch4)/top along y: how the "
        "light is shared over the four top anodes.",
        "Areas with LED gains only (the load correction f<sub>top</sub> of the v2 gains undone), positions from the v4 "
        "processing (pos_rec_map v0).",
    ])

    st += [PageBreak(), P("2. Clean data selection", h2), P(
        "Each cut removes a population that earlier steps showed to be physically different from ordinary events "
        "(history note, section 8). Cut flow (Δ750 V, 28/29-09, percentages relative to the single scatters):")]
    st.append(cutflow_table())
    st.append(Spacer(1, 4))
    st += bullets([
        "<b>Single scatter</b> (no alternative S2): multiple scatters mix two positions in one top-light pattern.",
        "<b>S1 ≥ 20 PE, seen by top and bottom PMT:</b> removes tiny S1s that are often noise or belong to another "
        "interaction (44 % of the small S2s at the centre had S1 &lt; 20 PE).",
        "<b>Drift time &gt; 3 µs:</b> removes near-gate events (~2 mm below the gate; S2/S1 ≈ 600–1000). Their S2 area "
        "fraction top is 0.04–0.05 lower than for bulk events at the same position.",
        f"<b>S2 width at the gate &gt; 450 ns</b> (width50² − 3600 ns²/µs × drift time): removes 'short-gap' S2s — narrower "
        f"than the gas-gap crossing allows ({SW['no source 3–20 kPE']['width_centre']:.0f} ns vs "
        f"{SW['no source 3–20 kPE']['width_ring']:.0f} ns for small S2s), with balanced top light, reconstructed at the "
        "centre and with a low area fraction top. They made the central dip.",
        "<b>S1 area fraction top consistent with the drift time</b> (within 3σ of the median S1 AFT at that drift time, σ per "
        "S1 size): removes S1–S2 pairs that do not belong together. Not applied to the S1-versus-z comparison (circular).",
        "Effect on the energy scale: the cuts leave the cS1 and cS2 spectra unchanged in shape; the Cs-137 photopeak cS2 "
        "spread stays at 43 %.",
    ])
    st.append(img(RES / "s2width_map" / "s2width_map.png", W, "Why the width cut: S2 width at the gate on x–y per S2 size (top) "
                  "and, for small no-source S2s, AFT versus width — narrow central S2s have AFT 0.50, normal-width central S2s "
                  "0.65 like the ring (bottom)."))

    st += [PageBreak(), P("3. Comparison on the clean data", h2), P(
        "Simulation band = the 10 best grid points of that sample's own fit (best point in the figure title), each scaled "
        "with its own ε; data = points with statistical errors; χ² includes a systematic floor (S2 0.010, S1 0.004, u/v "
        "0.010). The table gives χ² and ε at the joint best optics (section 4). The no-source u/v profiles have few points: "
        "the clean 3–20 kPE sample in the ±3 mm strips is small.")]
    st.append(img(RES / "clean_fit_none" / "best_fit.png", W * 0.92, "Clean no-source data (S2 3–20 kPE for S2 vs r and u/v; "
                  "S1 &gt; 20 PE for S1 vs z)."))
    st.append(img(RES / "clean_fit_photopeak" / "best_fit.png", W * 0.92, "Clean Cs-137 photopeak events."))
    st.append(table([
        ["", "no source (clean)", "Cs-137 photopeak (clean)"],
        ["χ² S2 vs r / S1 vs z / u,v at the joint best optics",
         f"{en['chi2_s2r']:.1f} / {en['chi2_s1z']:.1f} / {en['chi2_uv']:.1f}  ({en['ndf']['s2r']} / {en['ndf']['s1z']} / {en['ndf']['uv']} dof)",
         f"{ep['chi2_s2r']:.1f} / {ep['chi2_s1z']:.1f} / {ep['chi2_uv']:.1f}  ({ep['ndf']['s2r']} / {ep['ndf']['s1z']} / {ep['ndf']['uv']} dof)"],
        ["ε<sub>S2</sub> / ε<sub>S1</sub>", f"{en['eps_s2']:.2f} / {en['eps_s1']:.2f}", f"{ep['eps_s2']:.2f} / {ep['eps_s1']:.2f}"],
        ["AFT centre ÷ ring (data)", f"{FN['data_centre_over_ring']:.2f}", f"{FP['data_centre_over_ring']:.2f}"],
    ], [70 * mm, (W - 70 * mm) / 2, (W - 70 * mm) / 2]))
    st += [Spacer(1, 3)] + bullets([
        "Shapes reproduced for both samples: S2 versus r within ~0.01, S1 versus depth within the floor, the sector "
        "pattern inside the simulation band over ±24 mm. No central dip.",
        "Left over in the clean data: the outermost radius bin and the lower half (y &lt; 0) for shallow events carry "
        "small residual deviations (history note, section 8); they do not affect the fit.",
    ])

    st += [PageBreak(), P("4. Best optical parameters", h2), P(
        "Joint fit: the same optics for both clean samples, ε<sub>S2</sub> and ε<sub>S1</sub> free per sample (they absorb the "
        "absolute top/bottom scale, section 5), so the optics is set by the <b>shapes</b> only.")]
    pr = J["profiles"]
    st.append(table([["parameter", "best", "Δχ² of the other grid values"]] + [
        [n, f"{b[n]:g}", ", ".join(f"{v}: +{d:g}" for v, d in pr[n].items() if d > 0)] for n in pr],
        [45 * mm, 25 * mm, W - 70 * mm]))
    st.append(img(RES / "clean_joint" / "profiles.png", W * 0.55, "Profiled Δχ² of the joint fit."))
    st += bullets([
        f"Best grid point: PTFE R {b['PTFE R']}, specular {b['PTFE specular']}, steel R {b['steel R']}, Rayleigh "
        f"{b['Rayleigh [cm]']:.0f} cm; joint χ² {J['chi2_joint']:.0f} for {J['ndf_joint']} dof. Next best: PTFE R 0.90, "
        "specular 0.2, Rayleigh 60 cm (Δχ² +2.5) — the three PTFE / Rayleigh parameters trade against each other.",
        "Robust: low steel reflectivity (0.2; 0.35 costs Δχ² +39). Excluded: PTFE R 0.99 (+20), a purely diffuse PTFE "
        "(+17), Rayleigh 30 cm (+29).",
        "The grid is coarse (3 values per parameter); a finer grid around the best point would turn this into "
        "values with errors.",
    ])

    st += [PageBreak(), P("5. Relative efficiencies — what ε is", h2), P(
        "ε is defined on the <b>odds</b> of the area fraction top: AFT<sub>data</sub>/(1 − AFT<sub>data</sub>) = ε · "
        "AFT<sub>sim</sub>/(1 − AFT<sub>sim</sub>), i.e. ε = (top/bottom measured) ÷ (top/bottom simulated). A pure scale on "
        "the top signal relative to the bottom signal. The simulation counts photons hitting the photocathodes with equal QE; "
        "everything else ends up in ε:")]
    st += bullets([
        "<b>(a) Hardware ratio R</b>: QE × collection efficiency top ÷ bottom, and how well the LED gains calibrate each PMT. "
        "The same for S1 and S2, for every signal and every source. Unknown a priori (QE spread between tubes ±10–20 %).",
        "<b>(b) Load factor L</b>: the top PMT loses gain when its mean anode current is high (light of the preceding "
        "10–100 ms; S2-resolution note). It depends on the source rate, not on the event itself; the same for S1 and S2.",
        "<b>(c) Signal-size factor S</b>: a dependence on the size of the signal itself (readout, PMT response).",
        "So ε = R · L(source) · S(signal size).",
    ])
    st.append(img(RES / "clean_joint" / "efficiencies.png", W, "ε versus S2 size for the three sources (left), and ε divided "
                  "by its value above 20 kPE (right). Clean data, joint best optics."))
    rows = [["S2 [kPE]"] + [f"{a / 1e3:g}–{c / 1e3:g}" for a, c in zip(eps['no source']['s2_bins'][:-1], eps['no source']['s2_bins'][1:])]]
    for lab in ("no source", "Na-22", "Cs-137"):
        rows.append([f"ε, {lab}"] + [f"{v:.2f}" for v in eps[lab]["eps"]])
    for lab in ("no source", "Na-22", "Cs-137"):
        rows.append([f"ε ÷ plateau, {lab}"] + [f"{v:.2f}" for v in eps[lab]["shape"]])
    st.append(table(rows, [42 * mm] + [(W - 42 * mm) / 6] * 6))
    st += [Spacer(1, 3), P("<b>Reading the numbers</b>", base_style())]
    st += bullets([
        f"<b>Large signals (S2 &gt; 20 kPE): ε = R · L.</b> Plateau {eps['no source']['plateau']:.2f} without source, "
        f"{eps['Na-22']['plateau']:.2f} Na-22, {eps['Cs-137']['plateau']:.2f} Cs-137. The ordering follows the rate of large "
        "S2s (top-PMT load). For Cs-137 photopeak events ε<sub>S1</sub> = "
        f"{ep['eps_s1']:.2f} ≈ ε<sub>S2</sub> = {ep['eps_s2']:.2f}: S1 (1400 PE) and S2 (120 kPE) see the same factor — "
        "the load acts on the PMT, not on a signal type.",
        f"<b>R ≥ {eps['no source']['plateau']:.2f}</b>: equal if the no-source rate does not load the top PMT, larger if it "
        "does (the no-source rate of large S2s is not zero). Relative to no source the load costs the top PMT "
        f"{100 * (1 - eps['Na-22']['plateau'] / eps['no source']['plateau']):.0f} % with Na-22 and "
        f"{100 * (1 - eps['Cs-137']['plateau'] / eps['no source']['plateau']):.0f} % with Cs-137 — consistent with the top-PMT "
        "gain drop and single-photon losses measured independently (delayed-signal and S2-resolution notes).",
        "<b>Small S2s: S rises below 20 kPE with the same shape for all three sources</b> (×1.3 at 10–20, ×1.6 at 5–10, "
        "×2.2–2.8 at 3–5 kPE), also at a fixed position (r &lt; 8 mm, −40 &lt; z &lt; −10 mm: Cs-137 AFT 0.46 → 0.31). "
        "Independent of the rate, so not the load. Not the readout threshold (toy: &lt; 1 % at S2 ≥ 3 kPE). Open; candidates: "
        "the bottom PMT at −800 V (≈ 3–7 ADC per photon, 60 ADC trigger) losing part of small S2s, or a top-anode response "
        "to small pulses. Note: the S2-resolution analysis found S2 bottom / top flat within 5 % from 3·10<super>3</super> to "
        "1.5·10<super>5</super> PE at a fixed position — the two need to be reconciled (selection, gains).",
        f"<b>No-source S1: ε<sub>S1</sub> = {en['eps_s1']:.2f}</b> against the S2 plateau {eps['no source']['plateau']:.2f}: "
        "S1s of 20–2000 PE lose relatively more top charge. Expected from the amstrax hit-only integration (samples "
        "≥ 15 ADC only): a lone top photon keeps ~55 % of its charge, the toy gives top 0.56 / 0.70 / 0.85 kept at 30 / 100 / "
        "300 PE.",
        f"<b>The no-source S2 fit value ε<sub>S2</sub> = {en['eps_s2']:.2f}</b> is ε for S2 3–20 kPE (the size used for S2 vs r), "
        "i.e. plateau × S(3–20 kPE).",
    ])
    st.append(box(bullets([
        "Use ε as R · L(source) · S(size), never as one number: compare like with like (same source rate, same signal size).",
        "To pin R down: a low-rate LED or no-source run with the top PMT at reduced gain (next fill), so L → 1.",
        "To understand S: S2 bottom/top versus size with the SiPMs as an independent bottom reference (29-09 runs); "
        "reconcile with the S2-resolution linearity check; the amstrax integration fix for small signals.",
    ]), AMBER))

    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=13 * mm, bottomMargin=13 * mm,
                            title="XAMS optical simulation — results", author="XAMS")
    doc.build(st)
    print("written", out)


def base_style():
    from make_note import base
    return base


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "notes" / "XAMS_optical_simulation_results_2026-10-11.pdf"))
