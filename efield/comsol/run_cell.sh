#!/bin/bash
# One mesh cell (gate or cathode): generate, solve, plot.   efield/comsol/run_cell.sh gate|cathode --states a,b [--cases c --level L]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
COMSOL="${COMSOL:-/Applications/COMSOL62/Multiphysics/bin/comsol}"
PY="${PY:-python}"   # the active conda env (xamssim)
EL="$1"; shift
cd "$HERE"
"$PY" make_cell.py "$EL" "$@"
cd build
rm -f "XAMS_cell_$EL.class"
"$COMSOL" compile "XAMS_cell_$EL.java"
"$COMSOL" batch -inputfile "$HERE/build/XAMS_cell_$EL.class" -outputfile "$HERE/build/XAMS_cell_$EL.mph" > "cell_$EL.log" 2>&1 || true
[ -f "XAMS_cell_${EL}_Model.mph" ] && mv -f "XAMS_cell_${EL}_Model.mph" "XAMS_cell_$EL.mph"
grep -A3 -i "error" "cell_$EL.log" | head -20 || true
grep "CHECK" "cell_$EL.log" || true
"$PY" "$HERE/plot_cell.py" "$EL"
