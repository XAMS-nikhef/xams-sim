#!/bin/bash
# One MC production run on STBC, as a condor job (as xamsdata: the central MC folders, run database runs_mc).
#   production_job.sh <run file> [corrections version]
# 1 xams-sim (setup_xamssim.sh, settings from ~/.config/xamssim/env): Geant4 -> chain to raw records -> live data
#   (live_mc/<run>/) + run document (mc_raw_records/<run>-metadata.json) + registration in run.runs_mc
# 2 amstrax as for data (setup_py312.sh): live data -> raw_records (mc_raw_records/) -> event_info (mc_processed/)
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
source $X/setup_py312.sh || exit 1
python - "$RID" "$CV" "$RAW" "$PROC" <<'PY'
import sys, time, warnings
import strax
import amstrax
warnings.filterwarnings("ignore")
rid, cv, raw, proc = sys.argv[1:]
t = time.time()
st = amstrax.contexts.context_for_daq_reader(amstrax.contexts.xams(output_folder=raw, corrections_version=cv), rid)
st.make(rid, "raw_records", progress_bar=False)
print(f"raw_records ({raw}) in {time.time() - t:.0f} s", flush=True)
st = amstrax.contexts.xams(output_folder=proc, corrections_version=cv)
st.storage += [strax.DataDirectory(raw, readonly=True, provide_run_metadata=True)]
amstrax.xams_config.RUNDOC_DIRS.append(raw)                  # the run document file next to the raw records
ev = st.get_array(rid, "event_info", progress_bar=False)
print(f"event_info ({proc}): {len(ev)} events, {time.time() - t:.0f} s in total", flush=True)
PY
rc=$?; echo "exit $rc, $(date)"; exit $rc
