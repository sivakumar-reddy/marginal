"""
17b_mimic_attenuation_sweep.py

Replaces a chosen assumption with a measured threshold.

`17` reported divergence at three fixed efficacy shapes. The strong attenuation case gave
Jaccard 0.000 in all twelve cells, which is arithmetically correct and rhetorically
useless: benefit peaks at p = 0.25, the top decile by risk sits well above it, and the two
lists are complements by construction. A reader is entitled to suspect the parameter was
chosen until the answer was dramatic.

The defensible question is not how large divergence can be made. It is how much
attenuation is required before divergence appears at all. That is a threshold, it does not
depend on picking a value, and a programme can compare it against their own beliefs.

WHAT IS SWEPT
=============
    ARR(p) = p * (1 - p)^beta,  beta from 0 to BETA_MAX

beta = 0 is proportional benefit, where the effect ranking is a monotone transform of the
risk ranking and the lists are identical. Increasing beta pulls the benefit peak down the
risk distribution, to p* = 1 / (1 + beta). The scale constant is dropped because both
Jaccard and the shortfall ratio are invariant to it.

TWO ONSETS, REPORTED SEPARATELY
===============================
    beta at which Jaccard first falls below 0.80
        the point where the two strategies name substantially different people

    beta at which the shortfall first exceeds 5%
        the point where that difference costs measurable outcomes

`17` already showed these are not the same. At `at_admission A 30` under mild attenuation,
Jaccard was 0.370 while the shortfall was 4.5%: sixty three percent of the list changed
and almost nothing was gained. Reporting only the first overstates the case and reporting
only the second hides that a completely different population is being served for the same
result.

THE MECHANISM IS REPORTED ALONGSIDE
===================================
For each cell the top decile risk band is printed against the benefit peak p*. `17`
suggested divergence is governed by whether the selected slice sits on the peak or past
it, which is why the low base rate regime B cells stayed near Jaccard 0.87 while the
roughly 50% base rate cells went to zero. If that reading is right, the onset beta should
track the top decile risk in an orderly way across all twelve cells. If it does not, the
reading is wrong and should be dropped.

TIES
====
`17`'s ceiling model was not identified: benefit saturated for most of the population, so
the effect ranking was choosing among a large tied pool and `argsort` broke ties by row
order. Nothing in this sweep saturates, but the size of the largest tied benefit group is
reported at every step so that a degenerate configuration cannot pass unnoticed again.

WHAT THIS DOES NOT ESTABLISH
============================
Not the true efficacy shape. MIMIC has no intervention and none is claimed. The output is
a map from an assumption a programme can hold to a consequence they can act on.

Not that attenuation is the only way benefit can vary. Benefit could depend on covariates
rather than on baseline risk, which is a different model and a later script.

Usage:
    python 17b_mimic_attenuation_sweep.py

Reads:
    data/processed/mimic_risk_oof.parquet

Writes:
    docs/17b_mimic_attenuation_sweep.md
    cache/mimic_attenuation_stats.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

POINTS = ["at_admission", "at_discharge"]
REGIMES = ["A", "B", "C"]
WINDOWS = [30, 90]

BETA_MAX = 4.0
BETA_STEP = 0.05

CAPACITIES = [0.01, 0.05, 0.10, 0.20]
HEADLINE_CAPACITY = 0.10

JACCARD_MATERIAL = 0.80
SHORTFALL_MATERIAL = 0.05

COL_ID, COL_Y, COL_P = "hadm_id", "readmit", "risk_logit"

stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


def top_k(scores, k):
    return np.argsort(-scores, kind="stable")[:k]


def jaccard(a, b):
    a, b = set(a.tolist()), set(b.tolist())
    return len(a & b) / len(a | b) if (a | b) else np.nan


def onset(betas, values, threshold, below=True):
    """First beta where the series crosses the threshold, linearly interpolated."""
    v = np.asarray(values)
    hit = v < threshold if below else v > threshold
    if not hit.any():
        return None
    i = int(np.argmax(hit))
    if i == 0:
        return float(betas[0])
    x0, x1 = betas[i - 1], betas[i]
    y0, y1 = v[i - 1], v[i]
    if y1 == y0:
        return float(x1)
    return float(x0 + (threshold - y0) * (x1 - x0) / (y1 - y0))


oof_path = PROC / "mimic_risk_oof.parquet"
if not oof_path.exists():
    sys.exit(f"\nMissing {oof_path}.")

oof = pd.read_parquet(oof_path)
for c in (COL_ID, COL_Y, COL_P):
    if c not in oof.columns:
        sys.exit(f"\nMissing column {c}. Available: {sorted(oof.columns)}")

betas = np.round(np.arange(0.0, BETA_MAX + BETA_STEP / 2, BETA_STEP), 4)

w("# 17b. How much attenuation before the lists part company?")
w()
w("Generated by `17b_mimic_attenuation_sweep.py`. Do not edit by hand.")
w()
w(
    "`17` fixed the efficacy shape at three chosen values. This sweeps it continuously "
    "and reports the point at which divergence begins, which is a threshold rather than "
    "a choice."
)
w()
w(
    f"ARR(p) = p (1-p)^beta, beta from 0 to {BETA_MAX:.0f} in steps of {BETA_STEP}. "
    "beta 0 is proportional benefit and gives identical lists by construction. The "
    "benefit peak sits at p* = 1 / (1 + beta). The scale constant is dropped because "
    "both reported quantities are invariant to it."
)
w()
w("## Two onsets")
w()
w("| Onset | Meaning |")
w("|---|---|")
w(f"| Jaccard below {JACCARD_MATERIAL:.2f} | the lists name substantially different people |")
w(f"| Shortfall above {SHORTFALL_MATERIAL:.0%} | that difference costs measurable outcomes |")
w()
w(
    "`17` showed these are not the same point. Reporting only the first overstates the "
    "case. Reporting only the second hides that a different population is being served "
    "for the same result."
)
w()

results = {}
t0 = time.time()

for point in POINTS:
    for regime in REGIMES:
        for wd in WINDOWS:
            o = oof[
                (oof["point"] == point)
                & (oof["regime"] == regime)
                & (oof["window"] == wd)
            ]
            if len(o) == 0:
                sys.exit(f"\nNo rows for {point} {regime} {wd}.")

            y = o[COL_Y].to_numpy()
            p = o[COL_P].to_numpy(dtype=float)
            n = len(p)

            key = f"{point}_{regime}_{wd}"
            cell = {
                "point": point, "regime": regime, "window": wd,
                "n": int(n), "base_rate": float(y.mean()),
                "capacities": {},
            }

            for cap in CAPACITIES:
                k = max(1, int(round(cap * n)))
                risk_idx = top_k(p, k)
                cut = float(p[risk_idx].min())
                band = [cut, float(p[risk_idx].max())]

                jac, shortfall, max_tie = [], [], []
                for b in betas:
                    benefit = p * (1.0 - p) ** b
                    eff_idx = top_k(benefit, k)
                    jac.append(jaccard(risk_idx, eff_idx))
                    tot = benefit[eff_idx].sum()
                    shortfall.append(
                        float(1 - benefit[risk_idx].sum() / tot) if tot > 0 else np.nan
                    )
                    vals, counts = np.unique(
                        np.round(benefit[eff_idx], 12), return_counts=True
                    )
                    max_tie.append(int(counts.max()))

                cell["capacities"][f"{cap:.2f}"] = {
                    "k": int(k),
                    "risk_band": band,
                    "jaccard": [float(v) for v in jac],
                    "shortfall": [float(v) for v in shortfall],
                    "max_tie": max_tie,
                    "onset_jaccard": onset(betas, jac, JACCARD_MATERIAL, below=True),
                    "onset_shortfall": onset(betas, shortfall, SHORTFALL_MATERIAL, below=False),
                }

            results[key] = cell
            print(f"  done {key}  ({time.time() - t0:.0f}s elapsed)")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

cap_key = f"{HEADLINE_CAPACITY:.2f}"


def fmt(v):
    return f"{v:.2f}" if v is not None else "never"


def peak(b):
    return 1.0 / (1.0 + b) if b is not None else None


w("## Sanity check")
w()
zero_ok = all(
    abs(r["capacities"][cap_key]["jaccard"][0] - 1.0) < 1e-9 for r in results.values()
)
max_tie = max(max(r["capacities"][cap_key]["max_tie"]) for r in results.values())
w(f"Jaccard is 1.000 at beta 0 in every cell: **{'yes' if zero_ok else 'NO'}**")
w(f"Largest tied benefit group at any step: **{max_tie}**")
w()
w(
    "The first must hold or the sweep is broken. The second guards against the "
    "non identification that made `17`'s ceiling model unreadable."
)
w()

w(f"## Onset, {HEADLINE_CAPACITY:.0%} capacity")
w()
w(
    "Top decile risk band is the range of predicted risk in the selected slice. Peak at "
    "onset is where benefit peaks at the beta where divergence begins."
)
w()
w("| Point | Regime | Window | Base rate | Top decile band | Jaccard onset | Peak there | Shortfall onset |")
w("|---|---|---:|---:|---|---:|---:|---:|")
for r in results.values():
    c = r["capacities"][cap_key]
    lo, hi = c["risk_band"]
    pk = peak(c["onset_jaccard"])
    pk_s = f"{pk:.3f}" if pk is not None else "n/a"
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | {r['base_rate']:.1%} | "
        f"{lo:.3f} to {hi:.3f} | {fmt(c['onset_jaccard'])} | {pk_s} | "
        f"{fmt(c['onset_shortfall'])} |"
    )
w()

w("## The gap between the two onsets")
w()
w(
    "How much attenuation separates the point where the lists diverge from the point "
    "where the divergence starts costing outcomes. A wide gap is the interesting case: "
    "a completely different population served for the same result."
)
w()
w("| Point | Regime | Window | Jaccard onset | Shortfall onset | Gap |")
w("|---|---|---:|---:|---:|---:|")
for r in results.values():
    c = r["capacities"][cap_key]
    a, b = c["onset_jaccard"], c["onset_shortfall"]
    gap = f"{b - a:.2f}" if (a is not None and b is not None) else "n/a"
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | "
        f"{fmt(a)} | {fmt(b)} | {gap} |"
    )
w()

w("## Does onset track the risk band?")
w()
w(
    "`17` suggested divergence is governed by whether the selected slice sits on the "
    "benefit peak or past it. If so, cells whose top decile sits low should tolerate more "
    "attenuation before diverging."
)
w()
cuts, onsets = [], []
for r in results.values():
    c = r["capacities"][cap_key]
    if c["onset_jaccard"] is not None:
        cuts.append(c["risk_band"][0])
        onsets.append(c["onset_jaccard"])
if len(cuts) > 2:
    rho = float(np.corrcoef(cuts, onsets)[0, 1])
    w(f"Correlation between top decile cut point and Jaccard onset: **{rho:+.3f}** "
      f"across {len(cuts)} cells.")
else:
    w("Too few cells reached the Jaccard threshold to assess this.")
w()

w(f"## Onset across capacity")
w()
w("| Point | Regime | Window | 1% | 5% | 10% | 20% |")
w("|---|---|---:|---:|---:|---:|---:|")
for r in results.values():
    vals = " | ".join(
        fmt(r["capacities"][f"{c:.2f}"]["onset_jaccard"]) for c in CAPACITIES
    )
    w(f"| {r['point']} | {r['regime']} | {r['window']} | {vals} |")
w()

oj = [r["capacities"][cap_key]["onset_jaccard"] for r in results.values()]
os_ = [r["capacities"][cap_key]["onset_shortfall"] for r in results.values()]
oj_v = [v for v in oj if v is not None]
os_v = [v for v in os_ if v is not None]

w("## Summary")
w()
w("| Quantity | Value |")
w("|---|---:|")
w(f"| Cells | {len(results)} |")
w(f"| Reached the Jaccard threshold | {len(oj_v)} of {len(results)} |")
w(f"| Reached the shortfall threshold | {len(os_v)} of {len(results)} |")
if oj_v:
    w(f"| Jaccard onset, median beta | {np.median(oj_v):.2f} |")
    w(f"| Jaccard onset, range | {min(oj_v):.2f} to {max(oj_v):.2f} |")
if os_v:
    w(f"| Shortfall onset, median beta | {np.median(os_v):.2f} |")
w()
w(
    "A programme that believes benefit is close to proportional should rank by risk and "
    "this whole comparison is moot for them. A programme that believes benefit falls away "
    "at the top of the risk distribution can read off the attenuation at which their two "
    "options separate, and separately the attenuation at which the separation starts "
    "costing outcomes. Neither number is an estimate of their efficacy. Both are "
    "conditional on a belief they hold and this data cannot supply."
)
w()

stats["results"] = results
stats["betas"] = [float(b) for b in betas]
stats["thresholds"] = {
    "jaccard_material": JACCARD_MATERIAL,
    "shortfall_material": SHORTFALL_MATERIAL,
}
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "17b_mimic_attenuation_sweep.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "mimic_attenuation_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.0f}s")
print("Wrote docs/17b_mimic_attenuation_sweep.md")
print("Wrote cache/mimic_attenuation_stats.json")
