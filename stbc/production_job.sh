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
# Corrections come from amstrax_files (corrections version, default v5). A private run usually has no entries there: it
# then uses the true values of its own simulation (run document, xamssim.truth) for the run-dependent corrections and
# the MC position map; a production run without entries fails (they belong in amstrax_files first).
set -o pipefail
RUN=$(readlink -f "$1"); CV=${2:-v5}
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
PRIVATE=$(python3 -c "import configparser,os; c=configparser.ConfigParser(); c.read(os.path.expanduser('~/.xams_config')); print(0 if 'mc' in c else 1)")
source $X/setup_py312.sh || exit 1
python - "$RID" "$CV" "$RAW" "$PROC" "$ENTRIES" "$PRIVATE" <<'PY'
import datetime, getpass, json, os, socket, sys, time, warnings
import strax
import amstrax
warnings.filterwarnings("ignore")
rid, cv, raw, proc, entries_file, private = sys.argv[1:]
private = private == "1"
TRUTH = ("elife", "gain_to_pe_array", "drift_time_gate", "drift_time_cathode")   # from the run's own simulation
MC_MAP = "900000"                                                                   # pos_rec_map: the MC range


def correction(url, run):
    """Value of a file:// correction for a run, or KeyError if the file has no entry for it."""
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(url).query)
    data = amstrax.get_correction(q["filename"][0], branch=q.get("github_branch", ["master"])[0])
    try:
        return amstrax.xams_config.XAMSConfig.find_correction_value(None, data, run, correction_file=q["filename"][0])
    except ValueError as e:
        raise KeyError(url) from e


def private_corrections(st):
    """Overrides for corrections amstrax_files has no entry for (private runs only)."""
    truth = json.load(open(os.path.join(raw, f"{rid}-metadata.json")))["xamssim"]["truth"]
    over = {}
    for name, url in st.config.items():
        if not (isinstance(url, str) and url.startswith("file://")):
            continue
        try:
            correction(url, rid)
        except KeyError:
            if name in TRUTH:
                over[name] = truth[name]
            elif name == "pos_rec_map":
                over[name] = correction(url, MC_MAP)
            else:
                raise SystemExit(f"no {name} for run {rid} in amstrax_files and no simulation value for it")
    for k, v in over.items():
        print(f"  correction {k}: not in amstrax_files for {rid}: "
              + ("MC position map (range of run %s)" % MC_MAP if k == "pos_rec_map" else f"simulation value {v}"), flush=True)
    return over


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
if private:
    st.set_config(private_corrections(st))
ev = st.get_array(rid, "event_info", progress_bar=False)
print(f"event_info ({proc}): {len(ev)} events, {time.time() - t:.0f} s in total", flush=True)
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
rm -f "$ENTRIES"
echo "exit $rc, $(date)"; exit $rc
