#!/bin/bash
# Install xams-sim on STBC next to the py312 stack (nothing existing is changed).
#   software/xams-sim          xams-sim checkout (must exist: private repo, put there before running this script)
#   anaconda/g4                env: Geant4 11.3 (conda-forge) + cmake + compilers; only to build and run xamsg4
#   anaconda/xamssim           env: Python 3.12, xams-sim (editable) with strax 2.2.3, fuse, nestpy; amstrax and
#                              amstrax_files from the shared checkouts (software/amstrax, software/amstrax_files) via a
#                              .pth file, as in py312
#   software/xams-sim/g4/build/xamsg4   the Geant4 program
#   setup_xamssim.sh           activates the xamssim env
# Both envs in the existing conda base anaconda/miniforge (that of py312). Run as a member of group xenon.
# Log: anaconda/install_xamssim.log
set -euo pipefail
umask 002
X=/data/xenon/xams_v2
SIM=$X/software/xams-sim
CONDA=$X/anaconda/miniforge/bin/conda
[ -d "$SIM/xamssim" ] || { echo "no xams-sim checkout in $SIM"; exit 1; }
# resumable: steps already done (env present, program built) are skipped; setup_xamssim.sh is never overwritten
[ -e $X/setup_xamssim.sh ] && { echo "exists, stop: $X/setup_xamssim.sh"; exit 1; }
# package cache: the shared one of miniforge (owner xamsdata) is read-only for others: give your own with CONDA_PKGS_DIRS
export PIP_CACHE_DIR=/tmp/pip-cache-$USER PYTHONNOUSERSITE=1 CONDA_PKGS_DIRS=${CONDA_PKGS_DIRS:-$X/anaconda/miniforge/pkgs}

# --- Geant4 env and xamsg4
[ -d $X/anaconda/g4 ] || $CONDA create -y -p $X/anaconda/g4 --override-channels -c conda-forge geant4=11.3 cmake cxx-compiler nlohmann_json
# CMAKE_PREFIX_PATH: the env's libraries first (else CMake takes the system's, e.g. an old libexpat)
[ -x $SIM/g4/build/xamsg4 ] || $CONDA run -p $X/anaconda/g4 --no-capture-output bash -c \
    'cmake -S '$SIM'/g4 -B '$SIM'/g4/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=$CONDA_PREFIX && cmake --build '$SIM'/g4/build -j8'

# --- xamssim env
[ -d $X/anaconda/xamssim ] || $CONDA create -y -p $X/anaconda/xamssim --override-channels -c conda-forge python=3.12 pip
PY=$X/anaconda/xamssim/bin/python
$PY -m pip install -U pip wheel
$PY -m pip install -e "$SIM[chain,test]"
# amstrax's own dependencies (requirements.txt) + what the export, notebooks and tests use
$PY -m pip install "pymongo>=4.6" "multihist>=0.6.3" iminuit matplotlib packaging gitpython requests IPython sshtunnel \
    "paramiko<4" commentjson immutabledict ipykernel ipywidgets
SP=$($PY -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
printf "%s\n%s\n" $X/software/amstrax $X/software/amstrax_files > $SP/xams_checkouts.pth

cat > $X/setup_xamssim.sh <<'EOS'
# XAMS simulation (xams-sim) on STBC. Source, do not execute.
#   XAMSSIM_DATA            where the simulation output goes (Geant4, strax, maps registry): from the environment or
#                           from your ~/.config/xamssim/env (a line XAMSSIM_DATA=/path; also read by xamssim itself, so
#                           Jupyter kernels and condor jobs find it too)
#   XAMSSIM_AMSTRAX_STORE   where `xamssim amstrax` puts runs for amstrax (default: strax_data next to XAMSSIM_DATA)
#   XAMSSIM_STUDIES         your checkout of the simulations repository (studies with runs/*.yaml; default: the folder
#                           holding XAMSSIM_DATA)
_xams_base=/data/xenon/xams_v2/anaconda/miniforge
_xams_env=/data/xenon/xams_v2/anaconda/xamssim
if [ -z "${XAMSSIM_DATA:-}" ] && [ -r "$HOME/.config/xamssim/env" ]; then
    eval "$(grep -E '^[[:space:]]*XAMSSIM_[A-Z_]+=' "$HOME/.config/xamssim/env" | sed 's/^[[:space:]]*/export /')"
fi
if [ -z "${XAMSSIM_DATA:-}" ]; then
    echo "ERROR: set XAMSSIM_DATA (your simulation data folder, e.g. /data/xenon/xams_v2/users/<you>/xamssim/data)," >&2
    echo "       best as a line XAMSSIM_DATA=/path in ~/.config/xamssim/env" >&2
    return 1
fi
. "$_xams_base/etc/profile.d/conda.sh" || { echo "ERROR: cannot load conda from $_xams_base" >&2; return 1; }
conda activate "$_xams_env" || { echo "ERROR: cannot activate $_xams_env" >&2; return 1; }
export XAMSSIM_G4_ENV=/data/xenon/xams_v2/anaconda/g4
export XAMSSIM_AMSTRAX_STORE=${XAMSSIM_AMSTRAX_STORE:-$(dirname "$XAMSSIM_DATA")/strax_data}
export PYTHONNOUSERSITE=1      # ignore ~/.local packages (old versions there shadow the env)
echo "xams-sim: $(python --version 2>&1), env $_xams_env"
echo "  data   $XAMSSIM_DATA"
echo "  store  $XAMSSIM_AMSTRAX_STORE"
unset _xams_base _xams_env
EOS

$PY -m pip list 2>/dev/null | grep -iE "^(strax|straxen|xenon-fuse|nestpy|numpy|numba|scipy|pandas|pymongo) "
$PY -c "import strax, fuse, nestpy, amstrax, amstrax_files, xamssim; print('strax', strax.__version__, '| fuse', fuse.__version__, '| amstrax', amstrax.__file__)"
ls -l $SIM/g4/build/xamsg4
echo INSTALL DONE
