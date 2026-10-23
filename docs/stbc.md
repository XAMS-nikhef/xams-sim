# Running on STBC: private and production MC

There are two ways to run the simulation on STBC. They use the same software and the same scripts; **which account runs
them** decides where the output goes and whether the run enters the run database.

| | **Private MC** (studies, tests, trying things) | **Production MC** (runs meant for everyone) |
|---|---|---|
| account | your own (e.g. `z37`) | `xamsdata` |
| output | your own area, e.g. `/data/xenon/xams_v2/users/<you>/xamssim/` | the central MC folders `/data/xenon/xams_v2/mc`, `live_mc`, `mc_raw_records`, `mc_processed` (only `xamsdata` can write there) |
| run database | **never**: your account has no database account for MC | registered in `run.runs_mc` (with its processing) |
| visible in | your private simulation app ("Simulations (private)" tile), your notebooks, `xamssim list`; **not** in the xams-dashboard (that shows only runs in the run database) | the xams-dashboard ("Simulated runs (MC)") and the simulation app ("Simulations" tile) |
| run files | your own copy of the studies (`simulations` repository) | committed run files that `xamsdata` reads |

**Rule of thumb:** everything starts as a private MC. Only a run that others need (a reference, a comparison with
data, a result) becomes a production run. That keeps the run database free of trials.

The database is written only with the MC writer account (`[mc]` in `~/.xams_config`), which only `xamsdata` has. A
private run therefore cannot end up in the database, whichever command you use.

## One-time setup (private MC)

1. **Environment:** `source /data/xenon/xams_v2/setup_xamssim.sh` (or the alias `xamssim-setup`; in Jupyter the kernel
   "XAMS sim (Python 3.12, xamssim)").
2. **Settings** in `~/.config/xamssim/env` (no passwords; read by xamssim itself, so terminals, notebooks and condor
   jobs all find them):

    ```ini
    XAMSSIM_DATA=/data/xenon/xams_v2/users/<you>/xamssim/data
    XAMSSIM_AMSTRAX_STORE=/data/xenon/xams_v2/users/<you>/xamssim/strax_data
    XAMSSIM_LIVE=/data/xenon/xams_v2/users/<you>/xamssim/live_mc
    XAMSSIM_PROCESSED=/data/xenon/xams_v2/users/<you>/xamssim/processed
    XAMSSIM_G4_ENV=/data/xenon/xams_v2/anaconda/g4
    XAMSSIM_STUDIES=/data/xenon/xams_v2/users/<you>/xamssim/simulations
    ```

3. **Maps:** use the central ones (made on a Mac with COMSOL, read-only for you):

    ```bash
    mkdir -p /data/xenon/xams_v2/users/<you>/xamssim/data
    ln -s /data/xenon/xams_v2/mc/maps /data/xenon/xams_v2/users/<you>/xamssim/data/maps
    ```

    `xamssim maps --state sept --make --dry-run` must say "all maps present". A state whose maps are missing needs
    them made on the Mac first (COMSOL); ask for it rather than making your own.

4. **Run files:** a checkout of the `simulations` repository in `XAMSSIM_STUDIES` (your own study folder in it).
5. **Private app** (optional): the simulation app on your own data, as your account on stbc-i1, in a screen:

    ```bash
    XAMSSIM_WEB_SCREEN=xamssim_web_private XAMSSIM_WEB_PORT=8077 XAMSSIM_WEB_LOG=$HOME/xamssim_web_private.log \
        /data/xenon/xams_v2/software/xams-sim/web/start_stbc.sh
    ```

    The launcher tile "Simulations (private)" tunnels to it (port 8077). Restart it after a `git pull` of the software.

## A private MC

A run file (copy one, e.g. `2026-10-23_production_test/runs/prod_test_cs137_std.yaml`) with:

- `state`, `source`, `n_events`, `seed`;
- `physics: {source_rate_hz: 1000}` for anything you want to reconstruct with amstrax (fewer, fuller DAQ chunks);
- `run_number`: only needed for the reconstruction; for private runs use **99xxxx** (production uses 9002xx and up);
  numbers of private runs are never in the database, so they cannot clash there;
- `tags: [test]` if you like (shown wherever the run document is shown).

Small runs interactively on stbc-i2:

```bash
xamssim particle runs/my_run.yaml                      # Geant4
xamssim chain runs/my_run.yaml --target raw_records    # the chain up to the waveforms (or --target events)
```

The intermediate products are in `XAMSSIM_DATA/strax`; read them with `xamssim.chain.context(<run file>)` or the
notebook `2026-10-18_example/analysis/view_results.ipynb`.

Larger runs (or simulation + reconstruction in one go) on condor, at most 10 jobs at a time:

```bash
/data/xenon/xams_v2/software/xams-sim/stbc/submit_production.sh runs/my_run.yaml
```

This runs Geant4 → chain → live data → amstrax (raw records → event_info, corrections MC1) and puts everything in your
own area; logs in `XAMSSIM_DATA/logs/<run file name>/`. The script is the same for production; as your own account it
writes nothing to the database ("private run: not recorded in the run database").

## A production MC

Only for runs that others need. As `xamsdata` (whose settings point to the central MC folders):

1. **Run file** committed (so the production can always be traced to it), with a production run number (9002xx and
   up) and, while trying the flow, `tags: [test]`.
2. **Corrections:** nothing to do: an MC run takes its per-run corrections from its own run document (see
   "Corrections of MC runs" below).
3. **Submit** as `xamsdata`:

    ```bash
    /data/xenon/xams_v2/software/xams-sim/stbc/submit_production.sh <run file>
    ```

    The job registers the run in `run.runs_mc` when its live data are written, and records the amstrax processing
    (data entries, status) when it is done. Logs: `/data/xenon/xams_v2/mc/logs/<run file name>/`.

4. **Check:** the xams-dashboard (selector "Simulated runs (MC)": raw records, events, status, corrections) and the
   simulation app (how it was made).

Removing production runs again: `xamssim rundb --tag test --delete` (as `xamsdata`, asks for confirmation) removes the
run documents; their files are removed by hand from the central MC folders.

## Reconstructing an MC run (amstrax)

A simulated run is reconstructed exactly as a data run, in the standard amstrax environment
(`source /data/xenon/xams_v2/setup_py312.sh`), by its run number. The production job does this already; to do it
yourself (e.g. with other settings or corrections):

```python
import strax, amstrax
raw = "/data/xenon/xams_v2/mc_raw_records"          # private: your XAMSSIM_AMSTRAX_STORE
st = amstrax.contexts.xams(output_folder="<your output folder>", corrections_version="MC1")
st.storage += [strax.DataDirectory(raw, readonly=True, provide_run_metadata=True)]
amstrax.xams_config.RUNDOC_DIRS.append(raw)          # the run document file next to the raw records
st = amstrax.contexts.for_mc_run(st, "990001")       # the run's corrections (truth / calibrated) with their version
events = st.get_array("990001", "event_info")
```

- Raw records that do not exist yet are made from the live data with `amstrax.contexts.context_for_daq_reader(st,
  "<run>")` (as the production job does).
- The run document (channel map, thresholds, DAQ settings, corrections) comes from the file next to the raw records
  or, for production runs, from `run.runs_mc`.

## Corrections of MC runs

The cuts and settings come from amstrax_files, as for data: the MC global version `MC1` is the data version v5 with one
difference. The per-run corrections (electron lifetime, gains, gate and cathode drift times) come from the run's own
run document:

- `xamssim.corrections.truth`: the simulation's own values, written when the run is made;
- `xamssim.corrections.calibrated`: measured on the reconstructed MC with the calibration steps used for data, with a
  version (1, 2, …), the run it was measured on, method and date. Used when present, else the truth.

A data–MC comparison uses calibrated MC (both treated the same way); truth minus calibrated is the bias of the
calibration method (closure test). Real data never depend on any of this.

Two passes:

1. the job reconstructs with the truth (calibration version 0);
2. calibrate on the reconstructed MC (your analysis steps) and store the values, e.g. `cal.json` =
   `{"elife": 151200, "drift_time_gate": 4416, "method": "elife fit + drift edges", "analysis_commit": "a1b2c3d"}`:

    ```bash
    xamssim corrections 990001                                         # show truth / calibrated
    xamssim corrections --calibrated cal.json --from-run 990001 990001 # this run
    xamssim corrections --calibrated cal.json --from-run 990001 --state sept   # or all runs of the condition
    ```

    (`--runs A-B`, `--tag T` select too; `--dry-run` shows first.) A calibration applies only to runs of the same
    condition (state and maps): others are refused. Production runs (as `xamsdata`) are updated in `run.runs_mc` too;
3. reconstruct again: the same job, or the snippet above. The new calibration version gives new products next to the
   old ones; nothing is overwritten.

## Reruns

A run number is one fixed simulation and is never overwritten. To rerun a run file (new code, maps, more events, …),
give it the next free number and `supersedes: <old number>`; `xamssim live` refuses an existing number with a different
simulation. Under the same number only: reprocessing with amstrax and finishing a failed run (its calibrations are
kept). Outdated runs are removed when no longer needed.
