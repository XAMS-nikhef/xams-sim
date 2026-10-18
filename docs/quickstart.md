# Quick start

All commands from the repository root in the `xamssim` env:

```bash
conda activate xamssim && cd ~/Documents/XAMS/xams-sim
```

| command | does | output |
|---|---|---|
| `xamssim particle config/runs/s2_cs137_raised.yaml` | Cs-137 decays at the source position → every energy deposit in the xenon | `run/g4/s2_cs137_raised/deposits.*` |
| `xamssim particle config/runs/vis_cs137.yaml --vis` | particle viewer; type `/run/beamOn 10` | (window) |
| `xamssim optical optical/scans/fit_s2.yaml` | optical scan: S2 photons for a grid of optical parameters | `run/scans/fit_s2/` |
| `xamssim optical optical/scans/fit_s2.yaml --vis` | optical viewer for that scan (point 0; `--point N`, numbers from `--list`); type `/run/beamOn 20` | (window) |
| `xamssim status config/runs/<run>.yaml` | the resolved run (state, voltages, source), input hashes, which maps exist | (text) |
| `xamssim maps --state cmb50` | map status of one detector state | (text) |
| `xamssim validate config/runs/*.yaml` | check run files and everything they refer to | (text) |
| `efield/comsol/run.sh --cases cmb50` | COMSOL field model of the TPC for one HV case | `efield/comsol/build/`, `results/efield/comsol/` |

## A first particle run

```bash
xamssim particle config/runs/s2_cs137_raised.yaml --events 100000
python -c "
from xamssim import g4io
h, dep, ev = g4io.read('run/g4/s2_cs137_raised')
print(h['counts'], h['codes']['particle'])
print('events with energy in the liquid:', (ev['edep_lxe'] > 0).sum())"
```

## Your own run

Copy a run file and change what it points to:

```yaml
# config/runs/my_run.yaml
state: cmb50              # config/states/cmb50.yaml: HV, liquid level, pressure, lifetime
source: cs137_raised      # config/sources/cs137_raised.yaml: isotope, position
n_events: 200000
seed: 7
stop_after: geant4_interactions
```

```bash
xamssim validate config/runs/my_run.yaml && xamssim particle config/runs/my_run.yaml
```

See [configuration](configuration.md) for every field.
