"""S0: list all settings of the fuse micro-physics plugins (and the rest of the chain) with defaults; flag URL defaults."""
import warnings
warnings.filterwarnings("ignore")
import strax, straxen, fuse  # noqa: E402
from fuse import context as fc  # noqa: E402

groups = {
    "microphysics (dbscan)": fc.microphysics_plugins_clustering["dbscan"] + fc.microphysics_plugins_remaining,
    "microphysics (lineage)": fc.microphysics_plugins_clustering["lineage"],
}
for name in ("s1_simulation_plugins", "s2_simulation_plugins", "delayed_electron_simulation_plugins",
             "photon_summary_plugin", "pmt_and_daq_plugins"):
    if hasattr(fc, name):
        groups[name] = list(getattr(fc, name))
seen = set()
for g, plugins in groups.items():
    print(f"\n### {g}")
    for P in plugins:
        if P in seen:
            continue
        seen.add(P)
        print(f"  {P.__name__}: provides {P.provides}")
        for k, opt in P.takes_config.items():
            d = getattr(opt, "default", None)
            ds = repr(d)
            flag = "URL " if isinstance(d, str) and "://" in d else "    "
            if "resource://" in ds or "xedocs" in ds or "cmt" in ds:
                flag = "XEN "
            print(f"    {flag}{k} = {ds[:110]}")
