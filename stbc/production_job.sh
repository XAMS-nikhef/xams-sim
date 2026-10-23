#!/bin/bash
# One MC production run on STBC, as a condor job (as xamsdata: the central MC folders, run database runs_mc).
#   production_job.sh <run file> [corrections version]
# 1 xams-sim (setup_xamssim.sh, settings from ~/.config/xamssim/env): Geant4 -> chain to raw records -> live data
#   (live_mc/<run>/) + run document (mc_raw_records/<run>-metadata.json) + registration in run.runs_mc
# 2 amstrax as for data (setup_py312.sh): live data -> raw_records (mc_raw_records/) -> event_info (mc_processed/)
# 3 the processing recorded in run.runs_mc (data[] entries, processing_status), via xamssim rundb --record
set -o pipefail
RUN=$(readlink -f "$1"); CV=${2:-v5}
X=/data/xenon/xams_v2
RAW=$X/mc_raw_records; PROC=$X/mc_processed
echo "host $(hostname), user $(whoami), $(date), run file $RUN, corrections $CV"
umask 022
( source $X/setup_xamssim.sh || exit 1
  xamssim particle "$RUN" && xamssim chain "$RUN" --target raw_records && xamssim live "$RUN" ) || { echo "simulation failed"; exit 1; }
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
                n_chunks=len(files), size_mb=round(size / 1e6, 3), lineage_hash=key.split("-")[-1], is_online=False)


t = time.time()
st = amstrax.contexts.context_for_daq_reader(amstrax.contexts.xams(output_folder=raw, corrections_version=cv), rid)
st.make(rid, "raw_records", progress_bar=False)
print(f"raw_records ({raw}) in {time.time() - t:.0f} s", flush=True)
st = amstrax.contexts.xams(output_folder=proc, corrections_version=cv)
st.storage += [strax.DataDirectory(raw, readonly=True, provide_run_metadata=True)]
amstrax.xams_config.RUNDOC_DIRS.append(raw)                  # the run document file next to the raw records
ev = st.get_array(rid, "event_info", progress_bar=False)
print(f"event_info ({proc}): {len(ev)} events, {time.time() - t:.0f} s in total", flush=True)
data = [entry(st, t_, raw) for t_ in ("raw_records", "raw_records_sipm")]
data += [entry(st, t_, proc) for t_ in ("peak_basics", "event_basics", "event_positions", "event_info")]
json.dump(dict(data=data, corrections_version=cv), open(entries_file, "w"))
PY
rc=$?
# 3 record the processing in run.runs_mc (data[] entries, processing_status, history), as the auto-processing does for data
if [ $rc -eq 0 ]; then
    ( source $X/setup_xamssim.sh >/dev/null && xamssim rundb --record "$((10#$RID))" --entries "$ENTRIES" ) || rc=1
fi
rm -f "$ENTRIES"
echo "exit $rc, $(date)"; exit $rc
