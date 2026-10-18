#!/bin/bash
# Build and solve the COMSOL electric-field model of XAMS.
#   efield/comsol/run.sh [make_model.py options]      e.g.  run.sh --cases sept,cma,cmb
# Output: efield/comsol/build/XAMS_efield.mph (open in the COMSOL GUI), build/run.log,
#         results/efield/comsol/checks.json and maps_rz.npz (via parse_log.py).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
COMSOL="${COMSOL:-/Applications/COMSOL62/Multiphysics/bin/comsol}"
PY="${PY:-python}"   # the active conda env (xamssim)
cd "$HERE"
"$PY" make_model.py "$@"
cd build
rm -f XAMS_efield.class
"$COMSOL" compile XAMS_efield.java
"$COMSOL" batch -inputfile "$HERE/build/XAMS_efield.class" -outputfile "$HERE/build/XAMS_efield.mph" > run.log 2>&1 || true
[ -f XAMS_efield_Model.mph ] && mv -f XAMS_efield_Model.mph XAMS_efield.mph
grep -A3 -i "error" run.log | head -20 || true
"$PY" "$HERE/parse_log.py" "$HERE/build/run.log"
