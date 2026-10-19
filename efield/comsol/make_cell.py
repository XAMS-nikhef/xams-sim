#!/usr/bin/env python3
"""Field and drift lines through ONE cell of an etched mesh (gate or cathode), COMSOL 6.2, generated as Java.

The etched foils are square grids (geometry.yaml mesh_common: holes 2.45 mm, bars 0.15 mm wide, foil 0.15 mm thick,
pitch 2.6 mm). A quarter cell (x, y in [0, p/2], hole centre at the origin, bar centre at p/2) with zero-normal-field
side walls is exact for an infinite periodic grid. Above and below, the cell ends on planes at the potentials that the
TPC field gives there (drift field from (V_gate - V_cathode) / 51.8 mm; the anode and bottom screen as planes):
  gate cell:    z = -4 mm (drift region, V = Vg - E_d * 4 mm) ... liquid surface at +4 mm ... anode plane at +8 mm
  cathode cell: bottom screen plane at -7.8 mm ... cathode at 0 ... z = +4 mm (drift region, V = Vc + E_d * 4 mm)
All cases of the selection are solved in one auxiliary sweep. The plane y = 0 (through the hole centre and across a bar,
a symmetry plane) is printed to the log as MAP lines; plot_cell.py draws |E|, equipotentials, field and drift lines.

    python efield/comsol/make_cell.py gate|cathode --states sept,cmb50,refa   (writes build/XAMS_cell_<el>.java)
    efield/comsol/run_cell.sh gate|cathode --states ...                       (generate, solve, parse, plot)
    (--cases X --level L for HV cases without a state)
"""
import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "efield" / "comsol" / "build"


def jstr(a):
    return "new String[]{" + ", ".join(f'"{x}"' for x in a) + "}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("electrode", choices=("gate", "cathode", "stack", "stackx"),
                    help="stack = gate + liquid surface + anode mesh + top screen, anode aligned with the gate; "
                         "stackx = the same with the anode shifted by half a pitch in x")
    ap.add_argument("--states", default="", help="states (config/states): their HV cases and liquid level")
    ap.add_argument("--detector", help="detector for --cases without --states (default xams2026; with --states: theirs)")
    ap.add_argument("--cases", default="", help="extra HV cases of cases.yaml (without --states: needs --level)")
    ap.add_argument("--level", type=float, help="liquid level above the gate [mm] for --cases without --states")
    ap.add_argument("--hmax", type=float, default=0.06)
    ap.add_argument("--hbar", type=float, default=0.012)
    ap.add_argument("--map3d", action="store_true", help="also print the 3D field near the foil (M3 lines) for plot_cell3d.py")
    a = ap.parse_args()
    from xamssim.config import efield_detector, geometry_hash, load_geometry
    detector = efield_detector(a.states, a.detector)
    G = load_geometry(detector)
    ghash = int(geometry_hash(G)[:7], 16)          # marks the model: exports check it against the state's geometry
    MAT = yaml.safe_load(open(ROOT / "config" / "materials.yaml"))["materials"]
    eps_l = MAT["liquid_xenon"]["electrical"]["relative_permittivity"]
    eps_g = MAT["gas_xenon"]["electrical"]["relative_permittivity"]
    C = yaml.safe_load(open(ROOT / "efield" / "cases.yaml"))
    mc = G["mesh_common"]
    p, w, t = mc["pitch_mm"], mc["bar_width_mm"], mc["foil_thickness_mm"]
    h = p / 2
    from xamssim.config import ConfigError, efield_selection
    try:
        cases, level = efield_selection(a.states, a.cases, a.level)
    except ConfigError as e:
        raise SystemExit(f"make_cell: {e}")
    names = list(cases)
    L = 51.8
    stack = a.electrode.startswith("stack")
    za = next(m["z_mm"] for m in G["meshes"] if m["name"] == "anode")
    zts = next(m["z_mm"] for m in G["meshes"] if m["name"] == "top_screen")
    if a.electrode == "gate":
        z0, z1 = -4.0, 8.0
        rows = {n: (cases[n]["G"] - (cases[n]["G"] - cases[n]["C"]) / L * 4.0, cases[n]["A"], cases[n]["G"]) for n in names}
    elif stack:
        z0, z1 = -4.0, zts
        rows = {n: (0.0, cases[n]["TS"], cases[n]["G"], cases[n]["A"]) for n in names}
    else:
        z0, z1 = -7.8, 4.0
        rows = {n: (cases[n]["BS"], cases[n]["C"] + (cases[n]["G"] - cases[n]["C"]) / L * 4.0, cases[n]["C"]) for n in names}
    # cases with the same cell potentials give one solution (COMSOL merges them in the sweep): solve each once
    uniq = {}
    for n in names:
        uniq.setdefault(tuple(rows[n]) + (cases[n]["G"] - cases[n]["C"],), n)
    if len(uniq) < len(names):
        print(f"same cell potentials, solved once: {sorted(set(names) - set(uniq.values()))}")
    names = list(uniq.values())
    cls = f"XAMS_cell_{a.electrode}"
    L_ = []
    j = lambda s: L_.append("    " + s)  # noqa: E731
    j('Model model = ModelUtil.create("Model");')
    j(f'model.label("{cls}.mph");')
    j(f'model.param().set("ghash", "{ghash}", "geometry hash of detector {detector}");')
    j('model.param().set("Vbot", "0[V]"); model.param().set("Vtop", "0[V]"); model.param().set("Vel", "0[V]"); model.param().set("Ezd", "0[V/m]"); model.param().set("Va", "0[V]");')
    j('model.component().create("comp1", true);')
    j('GeomSequence g = model.component("comp1").geom().create("geom1", 3);')
    j('g.lengthUnit("mm");')
    j(f'g.create("box", "Block").set("pos", new double[]{{0, 0, {z0}}}).set("size", new double[]{{{h}, {h}, {z1 - z0}}});')
    j(f'g.create("barx", "Block").set("pos", new double[]{{{h - w / 2}, 0, {-t / 2}}}).set("size", new double[]{{{w / 2}, {h}, {t}}});')
    j(f'g.create("bary", "Block").set("pos", new double[]{{0, {h - w / 2}, {-t / 2}}}).set("size", new double[]{{{h}, {w / 2}, {t}}});')
    barlist = ["barx", "bary"]
    if stack:
        # anode bars: aligned (bar centres at x, y = h) or shifted by half a pitch in x (bar centre at x = 0)
        ax0 = 0.0 if a.electrode == "stackx" else h - w / 2
        j(f'g.create("abarx", "Block").set("pos", new double[]{{{ax0}, 0, {za - t / 2}}}).set("size", new double[]{{{w / 2}, {h}, {t}}});')
        j(f'g.create("abary", "Block").set("pos", new double[]{{0, {h - w / 2}, {za - t / 2}}}).set("size", new double[]{{{h}, {w / 2}, {t}}});')
        barlist += ["abarx", "abary"]
    j(f'g.create("bars", "Union"); g.feature("bars").selection("input").set({jstr(barlist)});')
    j('g.create("dom", "Difference"); g.feature("dom").selection("input").set(new String[]{"box"});')
    j('g.feature("dom").selection("input2").set(new String[]{"bars"});')
    if a.electrode == "gate" or stack:
        j(f'g.create("lvl", "WorkPlane").set("quickz", {level}).set("unite", true);')
        j(f'g.feature("lvl").geom().create("r1", "Rectangle").set("size", new double[]{{{h}, {h}}});')
    j("g.run();")
    sel = 'model.component("comp1").selection()'
    selt = lambda tg: f'model.component("comp1").selection("{tg}")'  # noqa: E731

    def box(tag, dim, xmin, xmax, ymin, ymax, zmin, zmax, cond):
        j(f'{sel}.create("{tag}", "Box"); {selt(tag)}.set("entitydim", {dim});')
        j(f'{selt(tag)}.set("xmin", {xmin}).set("xmax", {xmax}).set("ymin", {ymin}).set("ymax", {ymax}).set("zmin", {zmin}).set("zmax", {zmax});')
        j(f'{selt(tag)}.set("condition", "{cond}");')

    e = 1e-4
    box("s_bot", 2, -e, h + e, -e, h + e, z0 - e, z0 + e, "allvertices")
    box("s_top", 2, -e, h + e, -e, h + e, z1 - e, z1 + e, "allvertices")
    # bar surfaces: all boundaries inside the foil slab that are not on the side walls
    box("s_slab", 2, -e, h + e, -e, h + e, -t / 2 - e, t / 2 + e, "allvertices")
    box("s_xw", 2, -e, e, -e, h + e, -t, t, "allvertices")
    box("s_yw", 2, -e, h + e, -e, e, -t, t, "allvertices")
    box("s_xw2", 2, h - e, h + e, -e, h + e, -t, t, "allvertices")
    box("s_yw2", 2, -e, h + e, h - e, h + e, -t, t, "allvertices")
    j(f'{sel}.create("s_walls", "Union"); {selt('s_walls')}.set("entitydim", 2); {selt('s_walls')}.set("input", {jstr(["s_xw", "s_yw", "s_xw2", "s_yw2"])});')
    j(f'{sel}.create("s_bar", "Difference"); {selt('s_bar')}.set("entitydim", 2);')
    j(f'{selt('s_bar')}.set("add", new String[]{{"s_slab"}}); {selt('s_bar')}.set("subtract", new String[]{{"s_walls"}});')
    if stack:
        box("a_slab", 2, -e, h + e, -e, h + e, za - t / 2 - e, za + t / 2 + e, "allvertices")
        for k_, (x0_, x1_, y0_, y1_) in enumerate(((-e, e, -e, h + e), (-e, h + e, -e, e), (h - e, h + e, -e, h + e), (-e, h + e, h - e, h + e))):
            box(f"a_w{k_}", 2, x0_, x1_, y0_, y1_, za - t, za + t, "allvertices")
        j(f'{sel}.create("a_walls", "Union"); {selt('a_walls')}.set("entitydim", 2); {selt('a_walls')}.set("input", {jstr([f"a_w{k_}" for k_ in range(4)])});')
        j(f'{sel}.create("a_bar", "Difference"); {selt('a_bar')}.set("entitydim", 2);')
        j(f'{selt('a_bar')}.set("add", new String[]{{"a_slab"}}); {selt('a_bar')}.set("subtract", new String[]{{"a_walls"}});')
    j(f'model.component("comp1").material().create("lxe", "Common");')
    j('model.component("comp1").material("lxe").propertyGroup("def").set("relpermittivity", new String[]{"' + str(eps_l) + '"});')
    if a.electrode == "gate" or stack:
        box("s_liq", 3, -e, h + e, -e, h + e, z0 - e, level + e, "allvertices")
        j('model.component("comp1").material("lxe").selection().named("s_liq");')
        box("s_gas", 3, -e, h + e, -e, h + e, level - e, z1 + e, "allvertices")
        j('model.component("comp1").material().create("gxe", "Common");')
        j('model.component("comp1").material("gxe").propertyGroup("def").set("relpermittivity", new String[]{"' + str(eps_g) + '"});')
        j('model.component("comp1").material("gxe").selection().named("s_gas");')
    else:
        j('model.component("comp1").material("lxe").selection().all();')
    es = 'model.component("comp1").physics("es")'
    j('model.component("comp1").physics().create("es", "Electrostatics", "geom1");')
    # far side in the drift region: fixed drift FIELD (surface charge = D of the drift field), not a fixed potential, so
    # the field leaking through the holes shows up as a shift of the potential there instead of a wrong drift field
    fixedV = (("ptop", "s_top", "Vtop"), ("pel", "s_bar", "Vel")) if a.electrode == "gate" else (("pbot", "s_bot", "Vbot"), ("pel", "s_bar", "Vel"))
    if stack:
        fixedV = (("ptop", "s_top", "Vtop"), ("pel", "s_bar", "Vel"), ("pan", "a_bar", "Va"))
    for tag, s_, v in fixedV:
        j(f'{es}.create("{tag}", "ElectricPotential", 2); {es}.feature("{tag}").selection().named("{s_}"); {es}.feature("{tag}").set("V0", "{v}");')
    s_d, sign = ("s_bot", "") if a.electrode == "gate" or stack else ("s_top", "-")
    j(f'{es}.create("dfield", "SurfaceChargeDensity", 2); {es}.feature("dfield").selection().named("{s_d}");')
    j(f'{es}.feature("dfield").set("rhoqs", "{sign}epsilon0_const*{eps_l}*Ezd");')
    j('MeshSequence m = model.component("comp1").mesh().create("mesh1");')
    j(f'm.feature("size").set("custom", "on"); m.feature("size").set("hmax", {a.hmax}); m.feature("size").set("hmin", 0.002); m.feature("size").set("hgrad", 1.25);')
    j(f'm.create("szb", "Size"); m.feature("szb").selection().geom("geom1", 2); m.feature("szb").selection().named("s_bar");')
    j(f'm.feature("szb").set("custom", "on"); m.feature("szb").set("hmaxactive", true); m.feature("szb").set("hmax", {a.hbar});')
    if stack:
        j('m.create("sza", "Size"); m.feature("sza").selection().geom("geom1", 2); m.feature("sza").selection().named("a_bar");')
        j(f'm.feature("sza").set("custom", "on"); m.feature("sza").set("hmaxactive", true); m.feature("sza").set("hmax", {a.hbar});')
    j('m.create("ftet1", "FreeTet"); m.run();')
    j('System.out.println("CHECK mesh elements=" + m.getNumElem());')
    j('model.study().create("std1"); model.study("std1").create("stat", "Stationary");')
    st = 'model.study("std1").feature("stat")'
    j(f'{st}.set("useparam", true); {st}.set("sweeptype", "sparse");')
    pn_ = ["Vbot", "Vtop", "Vel", "Ezd"] + (["Va"] if stack else [])
    pl_ = [" ".join(f"{rows[n][k]:.3f}" for n in names) for k in range(3)] + [" ".join(f"{-(cases[n]['G'] - cases[n]['C']) / (L * 1e-3):.3f}" for n in names)]
    if stack:
        pl_.append(" ".join(f"{rows[n][3]:.3f}" for n in names))
    j(f'{st}.set("pname", {jstr(pn_)});')
    j(f'{st}.set("plistarr", {jstr(pl_)});')
    j(f'{st}.set("punit", {jstr(["V", "V", "V", "V/m"] + (["V"] if stack else []))});')
    j('model.study("std1").run();')
    nx, nz = 131, int(round((z1 - z0) / 0.01)) + 1
    j(f"int nx = {nx}, nz = {nz};")
    j("double[][] crd = new double[3][nx * nz];")
    j(f"for (int i = 0; i < nx; i++) for (int k = 0; k < nz; k++) {{ crd[0][i * nz + k] = Math.min(0.01 * i, {h - 1e-6}); crd[1][i * nz + k] = 1e-6; crd[2][i * nz + k] = {z0} + 0.01 * k; }}")
    j('model.result().numerical().create("map", "Interp");')
    j('model.result().numerical("map").set("expr", new String[]{"V", "es.Ex", "es.Ez"});')
    j('model.result().numerical("map").set("coorderr", "off");')
    j('model.result().numerical("map").set("coord", crd);')
    j('double[][][] mp = model.result().numerical("map").getData();')
    j(f"String[] cn = {jstr(names)};")
    j("for (int s = 0; s < cn.length; s++) { StringBuilder sb = new StringBuilder();")
    j("  for (int q = 0; q < crd[0].length; q++) sb.append(\"MAP \").append(cn[s]).append(\" \").append((float) crd[0][q]).append(\" \").append((float) crd[2][q]).append(\" \").append((float) mp[0][s][q]).append(\" \").append((float) mp[1][s][q]).append(\" \").append((float) mp[2][s][q]).append(\"\\n\");")
    j("  System.out.print(sb); }")
    if a.map3d:
        # 3D field in the quarter cell near the foil: x, y step h/50, z -2.5 ... 2.5 step 0.02 mm
        z3a, m3 = (-2.5, 676) if stack else (-2.5, 251)
        j(f"int n3 = 51, m3 = {m3};")
        j("double[][] c3 = new double[3][n3 * n3 * m3];")
        j(f"for (int i = 0; i < n3; i++) for (int k = 0; k < n3; k++) for (int l = 0; l < m3; l++) {{ int q = (i * n3 + k) * m3 + l; "
          f"c3[0][q] = Math.min({h} * i / 50.0, {h - 1e-6}); c3[1][q] = Math.min({h} * k / 50.0, {h - 1e-6}); c3[2][q] = {z3a} + 0.02 * l; }}")
        j('model.result().numerical().create("map3", "Interp");')
        j('model.result().numerical("map3").set("expr", new String[]{"es.Ex", "es.Ey", "es.Ez"});')
        j('model.result().numerical("map3").set("coorderr", "off");')
        j('model.result().numerical("map3").set("coord", c3);')
        j('double[][][] m3d = model.result().numerical("map3").getData();')
        j("for (int s = 0; s < cn.length; s++) { StringBuilder sb = new StringBuilder();")
        j("  for (int q = 0; q < c3[0].length; q++) sb.append(\"M3 \").append(cn[s]).append(\" \").append((float) c3[0][q]).append(\" \").append((float) c3[1][q]).append(\" \").append((float) c3[2][q]).append(\" \").append((float) m3d[0][s][q]).append(\" \").append((float) m3d[1][s][q]).append(\" \").append((float) m3d[2][s][q]).append(\"\\n\");")
        j("  System.out.print(sb); }")
    j("return model;")
    java = (f"// Generated by xams-sim/efield/comsol/make_cell.py ({a.electrode}; cases: {', '.join(names)})\n"
            "import com.comsol.model.*;\nimport com.comsol.model.util.*;\n\n"
            f"public class {cls} {{\n  public static Model run() throws java.io.IOException {{\n" + "\n".join(L_) +
            "\n  }\n\n  public static void main(String[] args) throws java.io.IOException {\n    run();\n  }\n}\n")
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / f"{cls}.java").write_text(java)
    meta = {"electrode": a.electrode, "stack": stack, "anode_z": za, "anode_offset_x": (h if a.electrode == "stackx" else 0.0), "z0": z0, "z1": z1, "half_pitch": h, "bar_width": w, "foil_thickness": t, "level": level,
            "cases": {n: {"Vbot": rows[n][0], "Vtop": rows[n][1], "Vel": rows[n][2], "Va": (rows[n][3] if stack else None),
                          "note": cases[n].get("note", "")} for n in names}}
    (BUILD / f"{cls}.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False))
    print(f"written {BUILD / (cls + '.java')} ({len(names)} cases)")


if __name__ == "__main__":
    main()
