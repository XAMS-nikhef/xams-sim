"""Waveforms and digitizer: photoelectrons per channel -> raw records as the V1725 / redax record them (plan S8).

Per cluster and light channel (xamssim.lightmap.CHANNEL_NAMES), from the chain:
    S1   s1_pe photoelectrons at the cluster time + scintillation (singlet / triplet) + transit-time spread, one by one
    S2   s2_pe photoelectrons spread over 4 ns bins: drift time (Gaussian, longitudinal diffusion) folded with the
         electron's EL emission profile (quantiles of xamssim.elmap), so large S2s cost O(bins), not O(photoelectrons)
Per photoelectron: a second one with the double-PE probability (PMTs) or crosstalk (SiPMs), an area ~ N(1, spe
resolution) (detector sensors.yaml). Per data channel (detector daq.yaml): area per 4 ns bin x single-PE gain
[ADC·samples] convolved with the measured single-PE pulse shape, Gaussian noise, baseline, polarity, 14-bit clipping.
Self-trigger: the samples above the threshold, extended by pre_trigger_samples before the first and post_samples after
the last crossing, merged, at least min_pulse_samples long; each pulse cut into records of record_length samples
(strax.raw_record_dtype). Not modelled: dark counts, afterpulses, baseline drifts, pile-up of noise-only triggers.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import strax
import yaml

from .config import Resolved, geometry_path

ADC_MAX = 2 ** 14 - 1


def daq_file(res: Resolved) -> Path:
    """The DAQ settings of the state's run period: detectors/<d>/daq_<period>.yaml for a state with `daq: <period>`,
    else daq.yaml (SR-2026.2)."""
    d = geometry_path(res.detector).parent
    period = res.state.get("daq")
    f = d / (f"daq_{period}.yaml" if period else "daq.yaml")
    if not f.exists():
        from .config import ConfigError
        raise ConfigError(f"state '{res.state_name}': no DAQ settings {f}")
    return f


def load_daq(res: Resolved) -> dict:
    """The DAQ settings of the state (daq_file) with the single-PE templates (lists, so that the content enters the
    lineage)."""
    f = daq_file(res)
    d = f.parent
    daq = yaml.safe_load(open(f))
    t = np.load(d / daq["digitizer"]["spe_templates"])
    tpl = {}
    for ch in daq["channels"]:
        v = np.clip(np.asarray(t[f"ch{ch}"], float), 0, None)                 # negative noise wiggles out
        tpl[str(ch)] = (v / v.sum()).round(5).tolist()                        # area 1 in samples
    daq["templates"] = tpl
    # sample of each template's maximum: peak_ch<N> in the file (SiPMs: 35, slow rise), else 10 (PMTs)
    daq["template_peaks"] = {str(ch): int(t[f"peak_ch{ch}"]) if f"peak_ch{ch}" in t.files else 10 for ch in daq["channels"]}
    daq["channels"] = {str(k): v for k, v in daq["channels"].items()}
    return daq


def _el_times(rng, quantiles_ns, u):
    """EL emission times [ns] for uniform numbers u, from the 5 ... 95 % quantiles (linear between them, 0 at 0 %,
    extended beyond 95 % with the last slope)."""
    q = np.concatenate([[0.0], quantiles_ns])
    p = np.concatenate([[0.0], np.round(np.arange(0.05, 0.951, 0.05), 3)])
    t = np.interp(u, p, q)
    hi = u > 0.95
    if hi.any():
        slope = (q[-1] - q[-2]) / 0.05
        t[hi] = q[-1] + (u[hi] - 0.95) * slope
    return t


class Digitizer:
    def __init__(self, daq: dict, spe_res: list, p_extra: list, rng):
        from .lightmap import CHANNEL_NAMES
        self.daq, self.rng = daq, rng
        dg = daq["digitizer"]
        self.dt, self.rl = int(dg["dt_ns"]), int(dg["record_length"])
        self.pre, self.min_len = int(dg["pre_trigger_samples"]), int(dg["min_pulse_samples"])
        self.chans = []
        for ch, c in daq["channels"].items():
            li = CHANNEL_NAMES.index(c["light"])
            self.chans.append(dict(ch=int(ch), light=li, raw=c["raw"], thr=float(c["threshold"]),
                                   sign=-1 if c["polarity"] == "negative" else 1, base=float(c["baseline"]),
                                   noise=float(c["noise"]), post=int(c["post_samples"]), gain=float(c["gain"]),
                                   tpl=np.asarray(daq["templates"][ch]), res=float(spe_res[li]), p=float(p_extra[li]),
                                   peak=int(daq.get("template_peaks", {}).get(ch, 10))))
        sc = daq["scintillation"]
        self.ts, self.tt, self.fs = float(sc["singlet_ns"]), float(sc["triplet_ns"]), float(sc["singlet_fraction"])
        self.tts = float(daq["pmt_transit_spread_ns"])

    # --- photoelectrons -> area per 4 ns bin, per channel, for one group of clusters (an event)
    def areas(self, c: dict, t0: int, n_bins: int, clusters) -> np.ndarray:
        rng, dt = self.rng, self.dt
        a = np.zeros(n_bins)
        for k in clusters:
            n1 = int(k["s1_pe"][c["light"]])
            if n1 > 0:
                tau = np.where(rng.random(n1) < self.fs, self.ts, self.tt)
                t = k["time"] - t0 + rng.exponential(tau) + rng.normal(0, self.tts, n1)
                n = 1 + rng.binomial(1, c["p"], n1)
                b = np.clip((t // dt).astype(int), 0, n_bins - 1)
                np.add.at(a, b, n + rng.normal(0, 1, n1) * c["res"] * np.sqrt(n))
            n2 = int(k["s2_pe"][c["light"]])
            if n2 > 0:
                # probability per bin: Gaussian drift spread folded with the EL profile (sampled finely, binned)
                m = min(n2, 4000)
                u = rng.random(m)
                t = (k["time"] - t0 + k["drift_time_mean"] + rng.normal(0, max(k["drift_time_spread"], 1e-3), m)
                     + _el_times(rng, k["el_time_quantiles"], u))
                b = np.clip((t // dt).astype(int), 0, n_bins - 1)
                if n2 > m:                                                  # large S2: multinomial over the shape
                    prob = np.bincount(b, minlength=n_bins).astype(float)
                    cnt = rng.multinomial(n2, prob / prob.sum())
                else:
                    cnt = np.bincount(b, minlength=n_bins)
                nz = np.flatnonzero(cnt)
                kk = cnt[nz]
                extra = rng.binomial(kk, c["p"])
                tot = kk + extra
                a[nz] += tot + rng.normal(0, 1, len(nz)) * c["res"] * np.sqrt(tot)
        return np.clip(a, 0, None)

    # --- one channel's waveform -> pulses (self-trigger) -> records
    def pulses(self, c: dict, t0: int, a: np.ndarray) -> list:
        # ADC above the baseline; shift by the template's peak sample so that its maximum falls in the PE's bin
        sig = np.convolve(a * c["gain"], c["tpl"])[c["peak"]: c["peak"] + len(a)]
        cand = np.flatnonzero(sig > c["thr"] - 6 * c["noise"])
        if not len(cand):
            return []
        # noise on the samples that can cross the threshold (and their surroundings), threshold crossings there
        gaps = np.flatnonzero(np.diff(cand) > self.pre + c["post"] + 1)
        iv = []
        for s0, e0 in zip(np.r_[cand[0], cand[gaps + 1]], np.r_[cand[gaps], cand[-1]]):
            lo, hi = max(s0 - 2, 0), min(e0 + 3, len(a))
            above = lo + np.flatnonzero(sig[lo:hi] + self.rng.normal(0, c["noise"], hi - lo) > c["thr"])
            if not len(above):
                continue
            g = np.flatnonzero(np.diff(above) > self.pre + c["post"])
            for p0, p1 in zip(np.r_[above[0], above[g + 1]], np.r_[above[g], above[-1]]):
                ps, pe = p0 - self.pre, p1 + c["post"] + 1
                pe = max(pe, ps + self.min_len)
                iv.append((max(ps, 0), min(pe, len(a))))
        if not iv:
            return []
        # pulses that touch or overlap are one pulse (the firmware keeps recording)
        iv.sort()
        merged = [list(iv[0])]
        for ps, pe in iv[1:]:
            if ps <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], pe)
            else:
                merged.append([ps, pe])
        out = []
        for ps, pe in merged:
            wave = sig[ps:pe] + self.rng.normal(0, c["noise"], pe - ps)
            adc = np.clip(np.round(c["base"] + c["sign"] * wave), 0, ADC_MAX).astype(np.int16)
            out.append((t0 + ps * self.dt, adc))
        return out

    def records(self, pulses: list, ch: int) -> np.ndarray:
        n = sum(-(-len(p) // self.rl) for _, p in pulses)
        r = np.zeros(n, dtype=strax.raw_record_dtype(self.rl))
        i = 0
        for t, p in pulses:
            for k in range(-(-len(p) // self.rl)):
                seg = p[k * self.rl:(k + 1) * self.rl]
                r[i]["time"], r[i]["dt"], r[i]["channel"] = t + k * self.rl * self.dt, self.dt, ch
                r[i]["length"], r[i]["pulse_length"], r[i]["record_i"] = len(seg), len(p), k
                r[i]["data"][: len(seg)] = seg
                i += 1
        return r

    def event(self, clusters, t_min: int | None = None) -> dict:
        """raw records (per raw type) for one group of clusters (t_min: no record before this time, the chunk start)."""
        dt = self.dt
        t_first = int(min(k["time"] for k in clusters))
        t_last = max(int(k["time"] + max(k["drift_time_mean"], 0) + 4 * max(k["drift_time_spread"], 0)
                         + (k["el_time_quantiles"][-1] * 2 if np.isfinite(k["el_time_quantiles"][-1]) else 0))
                     for k in clusters)
        t0 = (t_first - 100 * dt) // dt * dt
        if t_min is not None:
            t0 = max(t0, -(-int(t_min) // dt) * dt)
        n_bins = int((t_last - t0) // dt + 200)
        out = {}
        for c in self.chans:
            a = self.areas(c, t0, n_bins, clusters)
            if not a.any():
                continue
            r = self.records(self.pulses(c, t0, a), c["ch"])
            if len(r):
                out.setdefault(c["raw"], []).append(r)
        return {k: np.concatenate(v) for k, v in out.items()}
