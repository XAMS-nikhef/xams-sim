#!/bin/bash
# Start the simulation app on STBC in a detached screen (as xamsdata on stbc-i1, next to the xams-dashboard on 8070).
#   web/start_stbc.sh            start (nothing happens if the screen already runs)
#   web/start_stbc.sh stop       stop
#   web/start_stbc.sh status     screen and port
# Settings (data folder, run files) from ~/.config/xamssim/env of the user running it. Open it from your machine with
#   ssh -N -L 18075:127.0.0.1:8075 stbc-i1      then  http://localhost:18075   (the launcher does this)
# Not restarted after a reboot of the node: run this again.
#   XAMSSIM_WEB_PRIVATE=1 web/start_stbc.sh    your private app, as yourself: screen xamssim_web_private, port
#                        sim_port of ~/.xams/private.json, else of users.yaml (xams-dashboard), else 8077; every
#                        request needs your token (the one of the private dashboard). Production (xamsdata): actions
#                        need a key of a user with central_actions (web/access.py).
SETUP=/data/xenon/xams_v2/setup_xamssim.sh
WEB_DIR=$(cd "$(dirname "$0")/.." && pwd)
if [ "${XAMSSIM_WEB_PRIVATE:-0}" = 1 ]; then
    ACCESS=private
    SCREEN_NAME=${XAMSSIM_WEB_SCREEN:-xamssim_web_private}
    [ -n "${XAMSSIM_WEB_PORT:-}" ] || XAMSSIM_WEB_PORT=$(cd "$WEB_DIR" && bash -c "source $SETUP >/dev/null 2>&1; python -m web.access port" 2>/dev/null)
    PORT=${XAMSSIM_WEB_PORT:-8077}
else
    ACCESS=central
    SCREEN_NAME=${XAMSSIM_WEB_SCREEN:-xamssim_web}
    PORT=${XAMSSIM_WEB_PORT:-8075}
fi
LOG=${XAMSSIM_WEB_LOG:-$HOME/xamssim_web.log}

running() { screen -ls | grep -q "[.]$SCREEN_NAME[[:space:]]"; }

case "${1:-start}" in
    stop)
        running && screen -S "$SCREEN_NAME" -X quit && echo "stopped $SCREEN_NAME" || echo "$SCREEN_NAME not running" ;;
    status)
        running && echo "screen $SCREEN_NAME running" || echo "screen $SCREEN_NAME not running"
        ss -ltn 2>/dev/null | grep -q "127.0.0.1:$PORT " && echo "port $PORT listening" || echo "port $PORT not listening" ;;
    start)
        if running; then echo "$SCREEN_NAME already running (port $PORT)"; exit 0; fi
        # XAMSSIM_WEB_SUBMIT=1: the rerun button may submit condor jobs (as the user running the app; 0 to switch off)
        screen -S "$SCREEN_NAME" -dm bash -lc "source $SETUP && export XAMSSIM_WEB_SUBMIT=${XAMSSIM_WEB_SUBMIT:-1} XAMSSIM_WEB_ACCESS=${XAMSSIM_WEB_ACCESS:-$ACCESS} && exec xamssim web --host 127.0.0.1 --port $PORT >> $LOG 2>&1"
        sleep 5
        running && echo "started $SCREEN_NAME on 127.0.0.1:$PORT (log $LOG)" || { echo "failed to start; see $LOG"; exit 1; } ;;
    *)
        echo "usage: $0 [start|stop|status]"; exit 2 ;;
esac
