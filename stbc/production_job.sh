#!/bin/bash
# One MC run on STBC, simulated and reconstructed, as a condor job:
#   production_job.sh <run file> [corrections version]
# Where everything goes comes from the settings of the account that runs it (~/.config/xamssim/env):
#   XAMSSIM_DATA (Geant4, chain), XAMSSIM_LIVE (live data), XAMSSIM_AMSTRAX_STORE (raw records + run document),
#   XAMSSIM_PROCESSED (amstrax products; default: processed/ next to XAMSSIM_DATA).
# As xamsdata (production) these are the central MC folders and the run is registered in run.runs_mc; any other account
# (a private MC) has no [mc] database account, so nothing is ever written to the database.
# 1 xams-sim: Geant4 -> chain to raw records -> live data + run document (+ run.runs_mc for production)
# 2 amstrax as for data (setup_py312.sh): live data -> raw_records -> peak_basics ... event_info
# 3 production only: the processing recorded in run.runs_mc (data[] entries, processing_status)
# 4 the app's figures of the run (xamssim figures), so its detail page opens at once
# Corrections: an MC global version of amstrax_files (default MC1: the cuts and settings of the data version, the
# per-run corrections from the run's own run document: calibrated if stored, else the simulation's truth;
# amstrax.contexts.for_mc_run puts the calibration version into the lineage). See xamssim corrections.
# Reconstructions kept per run: the latest and, after a calibration, the truth one; older versions are deleted.
set -o pipefail
RUN=$(readlink -f "$1"); CV=${2:-MC1}
X=/data/xenon/xams_v2
source $X/setup_xamssim.sh >/dev/null || exit 1
RAW=$XAMSSIM_AMSTRAX_STORE; PROC=${XAMSSIM_PROCESSED:-$(dirname "$XAMSSIM_DATA")/processed}
mkdir -p "$RAW" "$PROC"
echo "host $(hostname), user $(whoami), $(date), run file $RUN, corrections $CV"
echo "data $XAMSSIM_DATA, raw records $RAW, processed $PROC"
umask 022
( xamssim particle "$RUN" && xamssim chain "$RUN" --target raw_records && xamssim live "$RUN" ) || { echo "simulation failed"; exit 1; }
RID=$(sed -nE 's/^run_number:[[:space:]]*([0-9]+).*/\1/p' "$RUN" | head -1)
RID=$(printf "%06d" "$RID")
ENTRIES=$(mktemp /tmp/xamssim_entries_${RID}_XXXX.json)
source $X/setup_py312.sh || exit 1
python - "$RID" "$CV" "$RAW" "$PROC" "$ENTRIES" <<'PY'
import datetime, getpass, json, os, socket, sys, time, warnings
import strax
import amstrax
warnings.filterwarnings("ignore")
rid, cv, raw, proc, entries_file = sys.argv[1:]


def entry(st, target, folder):
    """A data[] entry as the auto-processing writes it (amstrax auto_processing_new: add_data_entry)."""
    key = str(st.key_for(rid, target))
    d = os.path.join(folder, key)
    files = [f for f in os.listdir(d) if not f.endswith(".json")] if os.path.isdir(d) else []
    size = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)) if os.path.isdir(d) else 0
    return dict(time=datetime.datetime.now().isoformat(), type=target, location=d, host="stbc",
                user=getpass.getuser(), amstrax_version=amstrax.__version__, corrections_version=cv,
                n_chunks=len(files), size_mb=round(size / 1e6, 3), lineage_hash=key.split("-")[-1], is_online=False,
                mc_calibration=cal)


t = time.time()
st = amstrax.contexts.xams(output_folder=raw, corrections_version=cv)
if st.is_stored(rid, "raw_records"):                          # a rerun: amstrax never remakes stored raw records
    print(f"raw_records ({raw}) already stored: kept (remove them by hand to remake them from new live data)", flush=True)
else:
    st = amstrax.contexts.context_for_daq_reader(st, rid)
    st.make(rid, "raw_records", progress_bar=False)
    print(f"raw_records ({raw}) in {time.time() - t:.0f} s", flush=True)
st = amstrax.contexts.xams(output_folder=proc, corrections_version=cv)
st.storage += [strax.DataDirectory(raw, readonly=True, provide_run_metadata=True)]
amstrax.xams_config.RUNDOC_DIRS.append(raw)                  # the run document file next to the raw records
base = st
st = amstrax.contexts.for_mc_run(base, rid)                  # latest: the run's current corrections (version 0 = truth)
cal = int(amstrax.xams_config.get_rundoc_value(rid, amstrax.xams_config.MC_CALIBRATION_VERSION, default=0) or 0)
print(f"corrections {cv}, MC calibration version {cal} ({'truth' if not cal else 'calibrated'})", flush=True)
ev = st.get_array(rid, "event_info", progress_bar=False)
print(f"event_info ({proc}): {len(ev)} events, {time.time() - t:.0f} s in total", flush=True)
keep = [st]
if cal:                                                       # after a calibration also the truth reconstruction
    st_truth = amstrax.contexts.for_mc_run(base, rid, use="truth")
    print(f"event_info truth: {len(st_truth.get_array(rid, 'event_info', progress_bar=False))} events", flush=True)
    keep.append(st_truth)
# keep at most the latest and the truth reconstruction: every other version of this run's processed products goes
import shutil
removed = []
for d in sorted(os.listdir(proc)):
    if not d.startswith(rid + "-"):
        continue
    if d.endswith("_temp"):
        shutil.rmtree(os.path.join(proc, d)); removed.append(d); continue
    dtype, h = d.split("-")[1], d.split("-")[-1]
    try:
        wanted = {str(s_.key_for(rid, dtype).lineage_hash) for s_ in keep}
    except Exception:                                         # a type amstrax does not know (any more)
        wanted = set()
    if h not in wanted:
        shutil.rmtree(os.path.join(proc, d)); removed.append(d)
print(f"older reconstructions removed: {len(removed)}" + (f" ({', '.join(removed[:6])}{' ...' if len(removed) > 6 else ''})" if removed else ""), flush=True)
data = [entry(st, t_, raw) for t_ in ("raw_records", "raw_records_sipm")]
data += [entry(st, t_, proc) for t_ in ("peak_basics", "event_basics", "event_positions", "event_info")]
json.dump(dict(data=data, corrections_version=cv), open(entries_file, "w"))
PY
rc=$?
# 3 record the processing in run.runs_mc (data[] entries, processing_status, history), as the auto-processing does for data
if [ $rc -eq 0 ]; then
    ( source $X/setup_xamssim.sh >/dev/null && if python -c "import xamssim.rundb as r; raise SystemExit(0 if r.configured() else 1)"; then
          xamssim rundb --record "$((10#$RID))" --entries "$ENTRIES"; else echo "private run: not recorded in the run database"; fi ) || rc=1
fi
# 4 the app's figures of this run (configuration, results, reconstruction) now, so its page opens without waiting
( source $X/setup_xamssim.sh >/dev/null && xamssim figures "$RID" ) || echo "figures: not all made (the app makes them on first view)"
rm -f "$ENTRIES"
echo "exit $rc, $(date)"; exit $rc
