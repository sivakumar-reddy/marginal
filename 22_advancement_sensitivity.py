"""
22_advancement_sensitivity.py

How far must an assumption move before the allocation conclusion changes?

Follows the logic of `17b_mimic_attenuation_sweep.py`. The purpose is not to find a
parameter value that produces a striking result. It is to locate thresholds, so that a
reader can compare a threshold against their own beliefs instead of accepting mine.

`21` reported that at the operational portfolio, effect ranking delivers +155.5 expected
incremental gifts against +113.2 for risk ranking, and that both sit under a third of the
oracle's +505.8. Every one of those numbers is conditional on the illustrative parameters
in `18`. This script establishes which of them the conclusion actually depends on.

NO SECOND GENERATOR
===================
`18` now retains the common uniform draw and the two latent traits, so outcomes can be
recomputed under altered parameters without regenerating the population and without a
duplicate generator. Those columns are ground truth, are excluded from every model by
name, and are used here only to construct sweep conditions.

The historical visit policy is untouched throughout. It depends on capacity rating and
giving history, not on outcomes, so it stays confounded exactly as designed while the
outcomes move.

THREE SWEEPS
============
    effect magnitude
        Scales the gap between p1 and p0 for every prospect. At 0 the visit does nothing
        and effect ranking must be equivalent to arbitrary selection. At 1 the population
        is exactly as `18` generated it. This is the null check and the main axis.

    harm severity
        Scales the negative effect for the do not disturb group only, leaving every other
        group untouched. At 0 nobody is harmed and the domain loses the feature that
        distinguishes it from education and healthcare. This isolates how much of the
        result depends on harm existing at all.

    observability
        Blends a noisy signal of the latent traits into the feature matrix. At 0 the
        features are exactly what `18` provides and the result is `21`. As it rises, the
        CRM approaches perfect donor intelligence. `19b` found the observables explain
        under five percent of the variance in true effect, so this sweep answers the
        question that finding raises: what would better information be worth.

    capacity is swept in `21` and is not repeated here.

WHAT IS REPORTED
================
At each sweep point, both deployable strategies and the oracle are refitted and
reallocated at the operational capacity. Reported: expected incremental gifts, the share
of the oracle captured, harm in the selected portfolio, and the overlap between the risk
and effect lists.

Onsets are interpolated crossings, not the nearest grid point.

    equivalence onset   where risk and effect deliver within 5% of each other
    divergence onset    where the two lists overlap below 0.80 Jaccard
    dominance onset     where effect exceeds risk by more than 5%

WHAT THIS DOES NOT ESTABLISH
============================
Not the true value of any parameter. `08_sources.md` records every advancement benchmark
as open. This maps consequences conditional on a parameter, which is the only honest thing
a constructed population can do.

Usage:
    python 22_advancement_sensitivity.py

Reads:
    data/processed/advancement_population.parquet

Writes:
    docs/22_advancement_sensitivity.md
    cache/advancement_sensitivity_stats.json
"""

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

SEED = 20260823
N_FOLDS = 5
HEADLINE_CAPACITY = 0.03

MATERIAL_MARGIN = 0.05
JACCARD_MATERIAL = 0.80

SWEEPS = {
    "effect_magnitude": [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    "harm_severity": [0.0, 0.25, 0.5, 1.0, 1.5, 2.0],
    "observability": [0.0, 0.1, 0.25, 0.5, 0.75, 1.0],
}

GROUND_TRUTH = ["group", "y0", "y1", "tau", "p0", "p1",
                "u_draw", "latent_capacity", "latent_affinity"]
OUTCOME_DERIVED = ["gift_amount", "is_major_gift"]
OUTCOME, TREATMENT, ID = "gave", "visited", "prospect_id"
CATEGORICAL = ["region", "grad_decade"]

stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


def top_k(s, k):
    return np.argsort(-s, kind="stable")[:k]


def jaccard(a, b):
    a, b = set(a.tolist()), set(b.tolist())
    return len(a & b) / len(a | b) if (a | b) else np.nan


def lr():
    return LogisticRegression(max_iter=3000, solver="lbfgs")


def onset(xs, ys, threshold, below):
    v = np.asarray(ys, dtype=float)
    hit = v < threshold if below else v > threshold
    if not hit.any():
        return None
    i = int(np.argmax(hit))
    if i == 0:
        return float(xs[0])
    x0, x1, y0_, y1_ = xs[i - 1], xs[i], v[i - 1], v[i]
    if y1_ == y0_:
        return float(x1)
    return float(x0 + (threshold - y0_) * (x1 - x0) / (y1_ - y0_))


t0 = time.time()
df = pd.read_parquet(PROC / "advancement_population.parquet")
n = len(df)

FEATURES = [
    c for c in df.columns
    if c not in GROUND_TRUTH + OUTCOME_DERIVED + [OUTCOME, ID, TREATMENT]
]
for c in GROUND_TRUTH:
    assert c not in FEATURES, f"leakage: {c}"

base = pd.get_dummies(df[FEATURES], columns=CATEGORICAL, drop_first=True).astype(float)
D_base = StandardScaler().fit_transform(base.to_numpy())

u = df["u_draw"].to_numpy()
p0 = df["p0"].to_numpy()
p1_base = df["p1"].to_numpy()
group = df["group"].to_numpy()
v = df[TREATMENT].to_numpy()
lat = StandardScaler().fit_transform(
    df[["latent_capacity", "latent_affinity"]].to_numpy()
)

y0 = (u < p0).astype(int)
assert (y0 == df["y0"].to_numpy()).all(), "y0 must reconstruct from the retained draw"
assert ((u < p1_base).astype(int) == df["y1"].to_numpy()).all(), "y1 must reconstruct"

rng = np.random.default_rng(SEED)
perm = rng.permutation(n)
folds = np.empty(n, dtype=int)
for i, part in enumerate(np.array_split(perm, N_FOLDS)):
    folds[part] = i

k = max(1, int(round(HEADLINE_CAPACITY * n)))
noise_rng = np.random.default_rng(SEED + 4242)
lat_noise = noise_rng.normal(0, 1, lat.shape)


def build_p1(sweep, val):
    if sweep == "effect_magnitude":
        return np.clip(p0 + val * (p1_base - p0), 0.001, 0.999)
    if sweep == "harm_severity":
        gap = p1_base - p0
        scaled = np.where(group == "do_not_disturb", val * gap, gap)
        return np.clip(p0 + scaled, 0.001, 0.999)
    return p1_base


def build_D(sweep, val):
    if sweep != "observability":
        return D_base
    signal = val * lat + np.sqrt(max(1e-9, 1 - val ** 2)) * lat_noise
    return np.hstack([D_base, signal])


def evaluate(D, y1, tag):
    y_obs = np.where(v == 1, y1, y0)
    D_full = np.hstack([D, v[:, None]])
    D_at0 = np.hstack([D, np.zeros((n, 1))])

    p0h = np.full(n, np.nan)
    tauh = np.full(n, np.nan)
    for f in range(N_FOLDS):
        tr, te = folds != f, folds == f
        s = lr().fit(D_full[tr], y_obs[tr])
        p0h[te] = s.predict_proba(D_at0[te])[:, 1]
        b0, b1 = tr & (v == 0), tr & (v == 1)
        m0 = lr().fit(D[b0], y_obs[b0])
        m1 = lr().fit(D[b1], y_obs[b1])
        tauh[te] = m1.predict_proba(D[te])[:, 1] - m0.predict_proba(D[te])[:, 1]
    return p0h, tauh, y_obs


results = {}
for sweep, values in SWEEPS.items():
    rows = []
    for val in values:
        p1 = build_p1(sweep, val)
        y1 = (u < p1).astype(int)
        tau_true = p1 - p0
        D = build_D(sweep, val)

        p0h, tauh, _ = evaluate(D, y1, f"{sweep}={val}")

        sel = {
            "risk": top_k(p0h, k),
            "effect": top_k(tauh, k),
            "oracle": top_k(tau_true, k),
        }
        inc = {s: float(tau_true[i].sum()) for s, i in sel.items()}
        row = {
            "value": float(val),
            "incremental": inc,
            "effect_captured": {
                s: float(inc[s] / inc["oracle"]) if inc["oracle"] else np.nan
                for s in ["risk", "effect"]
            },
            "effect_over_risk": float(
                inc["effect"] / inc["risk"] - 1
            ) if inc["risk"] > 0 else np.nan,
            "jaccard_risk_effect": float(jaccard(sel["risk"], sel["effect"])),
            "harm_share": {
                s: float((tau_true[i] < 0).mean()) for s, i in sel.items()
            },
            "corr_tauhat_true": float(np.corrcoef(tauh, tau_true)[0, 1]),
        }
        rows.append(row)
        print(f"  {sweep}={val:<5} effect={inc['effect']:+8.1f} risk={inc['risk']:+8.1f} "
              f"oracle={inc['oracle']:+8.1f} ({time.time() - t0:.0f}s)")

    xs = [r["value"] for r in rows]
    results[sweep] = {
        "values": xs,
        "rows": rows,
        "onsets": {
            "divergence_jaccard": onset(
                xs, [r["jaccard_risk_effect"] for r in rows], JACCARD_MATERIAL, True
            ),
            "dominance": onset(
                xs, [r["effect_over_risk"] for r in rows], MATERIAL_MARGIN, False
            ),
        },
    }

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

w("# 22. Advancement sensitivity")
w()
w("Generated by `22_advancement_sensitivity.py`. Do not edit by hand.")
w()
w(
    "Simulation. Every result in `21` is conditional on the illustrative parameters in "
    "`18`. This script establishes which of them the conclusion actually depends on, by "
    "locating thresholds rather than by choosing values."
)
w()
w(
    f"All sweeps evaluated at the operational capacity, {HEADLINE_CAPACITY:.0%}, "
    f"{k:,} of {n:,}. Outcomes are recomputed from the retained uniform draw, so no second "
    "generator exists and the confounded historical policy is untouched throughout."
)
w()
w("## What is swept")
w()
w("| Sweep | At the baseline value | Meaning |")
w("|---|---|---|")
w("| effect_magnitude | 1.0 reproduces `18` | scales the gap between p1 and p0 for everyone |")
w("| harm_severity | 1.0 reproduces `18` | scales the negative effect for do not disturb only |")
w("| observability | 0.0 reproduces `18` | blends a noisy signal of the latent traits into the features |")
w()
w("| Onset | Definition |")
w("|---|---|")
w(f"| divergence | risk and effect lists overlap below {JACCARD_MATERIAL:.2f} Jaccard |")
w(f"| dominance | effect exceeds risk by more than {MATERIAL_MARGIN:.0%} |")
w()

for sweep in SWEEPS:
    r = results[sweep]
    w(f"## {sweep}")
    w()
    w("| Value | Risk | Effect | Oracle | Effect over risk | Risk captured | "
      "Effect captured | Jaccard | Effect harm |")
    w("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in r["rows"]:
        w(
            f"| {row['value']:.2f} | {row['incremental']['risk']:+.1f} | "
            f"{row['incremental']['effect']:+.1f} | {row['incremental']['oracle']:+.1f} | "
            f"{row['effect_over_risk']:+.1%} | "
            f"{row['effect_captured']['risk']:.1%} | "
            f"{row['effect_captured']['effect']:.1%} | "
            f"{row['jaccard_risk_effect']:.3f} | {row['harm_share']['effect']:.1%} |"
        )
    w()
    o = r["onsets"]
    w(f"Divergence onset: **{o['divergence_jaccard'] if o['divergence_jaccard'] is not None else 'never'}**. "
      f"Dominance onset: **{o['dominance'] if o['dominance'] is not None else 'never'}**.")
    w()

w("## Null check")
w()
null_row = results["effect_magnitude"]["rows"][0]
w(
    f"At effect_magnitude 0 the visit changes nothing for anyone, so every strategy must "
    f"deliver zero incremental gifts. Observed: risk {null_row['incremental']['risk']:+.1f}, "
    f"effect {null_row['incremental']['effect']:+.1f}, oracle "
    f"{null_row['incremental']['oracle']:+.1f}."
)
w()
w(
    "Anything other than zero on all three would mean the evaluation is crediting a "
    "strategy for outcomes it did not cause."
)
w()

w("## What the conclusion depends on")
w()
obs_rows = results["observability"]["rows"]
w("| Observability | Effect captured | Correlation of estimate with truth |")
w("|---:|---:|---:|")
for row in obs_rows:
    w(f"| {row['value']:.2f} | {row['effect_captured']['effect']:.1%} | "
      f"{row['corr_tauhat_true']:.4f} |")
w()
w(
    "`19b` found the observables explain under five percent of the variance in true "
    "effect, and `21` found no deployable strategy capturing more than a third of the "
    "oracle. This table is the direct answer to what that costs and what closing it would "
    "be worth."
)
w()

w("## Limitations")
w()
w(
    "No sweep establishes a true parameter value. Every advancement benchmark remains open "
    "in `08_sources.md`. The observability sweep blends in a signal derived from latent "
    "traits that exist only because the population was constructed, so it describes the "
    "value of better donor intelligence in principle and does not indicate that any "
    "particular data source would supply it."
)
w()
w(
    "`20` found the effect ranking not usable on stability grounds at the baseline "
    "parameters. That finding is not re measured here and applies to every row where "
    "effect ranking appears to win."
)
w()

stats["seed"] = SEED
stats["n"] = int(n)
stats["headline_capacity"] = HEADLINE_CAPACITY
stats["k"] = int(k)
stats["thresholds"] = {
    "material_margin": MATERIAL_MARGIN,
    "jaccard_material": JACCARD_MATERIAL,
}
stats["sweeps"] = results
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "22_advancement_sensitivity.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "advancement_sensitivity_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.1f}s")
print("Wrote docs/22_advancement_sensitivity.md")
print("Wrote cache/advancement_sensitivity_stats.json")
