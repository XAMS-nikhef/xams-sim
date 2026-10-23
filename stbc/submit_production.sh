#!/bin/bash
# Submit MC production runs to condor (as xamsdata), one job per run file:
#   submit_production.sh <run file> [<run file> ...]
# Logs in /data/xenon/xams_v2/mc/logs/<run file name>/. At most MAX_JOBS (10) xams-sim jobs of this account in condor
# at once (batch name xamssim_*); nothing is submitted beyond that.
MAX_JOBS=${MAX_JOBS:-10}
HERE=$(dirname "$(readlink -f "$0")")
LOGS=/data/xenon/xams_v2/mc/logs
for f in "$@"; do
    run=$(readlink -f "$f"); name=$(basename "$run" .yaml)
    n=$(condor_q "$USER" -af JobBatchName 2>/dev/null | grep -c '^xamssim_')
    if [ "$n" -ge "$MAX_JOBS" ]; then echo "$n xams-sim jobs in condor (max $MAX_JOBS): not submitting $name"; exit 1; fi
    mkdir -p "$LOGS/$name"
    cat > "$LOGS/$name/job.sub" <<SUB
executable     = $HERE/production_job.sh
arguments      = $run
batch_name     = xamssim_$name
log            = $LOGS/$name/job.log
output         = $LOGS/$name/job.out
error          = $LOGS/$name/job.err
request_memory = 16000MB
request_cpus   = 1
+UseOS         = "el9"
+JobCategory   = "medium"
queue
SUB
    condor_submit "$LOGS/$name/job.sub"
done
