# Quick start

All commands from the repository root in the `xamssim` env:

```bash
conda activate xamssim && cd ~/Documents/XAMS/xams-sim
```

| command | does | output |
|---|---|---|
| `xamssim particle config/runs/cs137_cmb50_001.yaml` | Cs-137 decays at the source position → every energy deposit in the xenon; skipped when the output is current for the run file (`--force` reruns) | `<data>/g4/cs137_cmb50_001/deposits.*` |
| `xamssim particle config/runs/vis_cs137.yaml --vis` | particle viewer; type `/run/beamOn 10` | (window) |
| `xamssim optical config/scans/example_s2.yaml` | example optical scan: S2 photons for two PTFE reflectivities | `<data>/scans/example_s2/` |
| `xamssim optical config/scans/example_s2.yaml --vis` | optical viewer for that scan (point 0; `--point N`, numbers from `--list`); type `/run/beamOn 20` | (window) |
| `xamssim chain config/runs/cs137_cmb50_001.yaml --target quanta` | clusters, local field and NEST quanta for those deposits | `<data>/strax/` |
| `xamssim chain <run> --target extracted_electrons` | S2: extracted electrons and EL photons per cluster (needs the extraction / EL map of the state) | `<data>/strax/` |
| `xamssim chain <run> --target photoelectrons` | S1 and S2 photoelectrons per channel per cluster (needs the light maps: `xamssim maps --state <s> --export light`) | `<data>/strax/` |
| `xamssim chain <run> --target drifted_electrons` | electrons drifted to the liquid surface (needs the drift map of the state and its lifetime, e.g. state `sept`; example: `../simulations/2026-10-18_example`) | `<data>/strax/` |
| `xamssim status config/runs/<run>.yaml` | the resolved run (state, voltages, source), input hashes, which maps exist | (text) |
| `xamssim maps --state cmb50` | map status of one detector state | (text) |
| `xamssim list [--run PATTERN] [--prune \| --delete]` | what is in the data folder: per run the Geant4 output and strax products, current or old for the run file as it is now; maps per state; `--prune` lists old data with sizes, `--delete` removes it after a confirmation; `--run 'example*'`: only runs whose id matches the pattern (shell wildcards `*`, `?`, the whole id; then no maps); `--delete --all --run PATTERN`: all data of those runs, current too | (text) |
| `xamssim validate config/runs/*.yaml` | check run files and everything they refer to | (text) |
| `efield/comsol/run.sh --states cmb50` | COMSOL field model of the TPC for a state (HV case + liquid level) | `efield/comsol/build/`, `<data>/efield/comsol/` |
| `xamssim maps --state cmb50 --export field` | field map of a state for the chain | `<data>/maps/field/<key>/` |

## A first particle run

```bash
xamssim particle config/runs/cs137_cmb50_001.yaml --events 100000
python -c "
from xamssim import g4io
from xamssim.config import DATA
h, dep, ev = g4io.read(DATA / 'g4' / 'cs137_cmb50_001')
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
