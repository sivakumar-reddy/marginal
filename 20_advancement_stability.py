"""
20_advancement_stability.py

Whether the prospect list survives a change in the training sample.

Follows the logic of `15_mimic_stability.py`. A fixed evaluation population is scored by
models fitted on bootstrap resamples of the training pool, so any movement in the ranking
comes from the model rather than from the population.

WHAT IS DIFFERENT HERE
======================
The clinical domain could only measure the stability of a risk ranking, because no
intervention variable existed. This domain has two rankings a shop could actually deploy,
and they are not equally stable in principle.

    risk ranking     ordered by estimated probability of giving without a visit
    effect ranking   ordered by estimated incremental effect of a visit

The effect ranking is a difference between two estimated quantities. Differences are
noisier than levels, and `19b` established that the observable features explain under five
percent of the variance in true effect. If a quantity is barely estimable, its ranking has
little reason to be reproducible, and a portfolio built on it may change substantially
from one refit to the next.

Both are measured. Reporting only the risk ranking would hide the cost of the alternative
this project spends most of its time recommending consideration of.

A THIRD QUESTION THIS DOMAIN CAN ASK
====================================
Membership stability is not the same as consequence stability. Two refits could select
largely different people and still deliver the same true value, or select largely the same
people and deliver different value. Because `18` retained both potential outcomes, the true
mean effect of each selected portfolio is known, so the variability of the consequence is
measured directly alongside the variability of the list.

`15` and `16` each found a version of this split in the clinical domain. Whether it recurs
here under a different mechanism is a genuine question rather than a confirmation.

THRESHOLDS
==========
Carried unchanged from the clinical domain so the three domains can be read against each
other without per domain adjustment.

    median pairwise Jaccard at the headline capacity
        at or above 0.80    stable enough to deploy
        0.60 to 0.80        marginal, usable only with the churn reported alongside
        below 0.60          not usable, the list would not survive being rerun

    coefficient of variation of the summed selected score
        at or below 0.02    the reported total is reproducible

Fixed before running. Not adjusted afterwards.

CAPACITY
========
1%, 3%, 5%, 10%, 20%. The 3% point is the operational portfolio from `18`, 1,500 of
50,000, and is reported as the headline.

Usage:
    python 20_advancement_stability.py

Reads:
    data/processed/advancement_population.parquet

Writes:
    docs/20_advancement_stability.md
    cache/advancement_stability_stats.json
"""

import json
import time
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

SEED = 20260823
N_FOLDS = 5
EVAL_FOLD = 4
R = 10

CAPACITIES = [0.01, 0.03, 0.05, 0.10, 0.20]
HEADLINE_CAPACITY = 0.03

JACCARD_STABLE = 0.80
JACCARD_MARGINAL = 0.60
CV_STABLE = 0.02

GROUND_TRUTH = ["group", "y0", "y1", "tau", "p0", "p1"]
OUTCOME_DERIVED = ["gift_amount", "is_major_gift"]
OUTCOME, TREATMENT, ID = "gave", "visited", "prospect_id"
CATEGORICAL = ["region", "grad_decade"]

ESTIMATORS = ["logit", "hgb"]
RANKINGS = ["risk", "effect"]

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


def make(est):
    if est == "logit":
        return LogisticRegression(max_iter=3000, solver="lbfgs")
    return HistGradientBoostingClassifier(
        random_state=SEED, early_stopping=True, validation_fraction=0.15
    )


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
D = StandardScaler().fit_transform(base.to_numpy())

y = df[OUTCOME].to_numpy()
v = df[TREATMENT].to_numpy()
true_tau = df["tau"].to_numpy()
true_group = df["group"].to_numpy()

rng = np.random.default_rng(SEED)
perm = rng.permutation(n)
folds = np.empty(n, dtype=int)
for i, part in enumerate(np.array_split(perm, N_FOLDS)):
    folds[part] = i

te = folds == EVAL_FOLD
tr_pool = np.flatnonzero(folds != EVAL_FOLD)
n_eval = int(te.sum())
D_te = D[te]
tau_te = true_tau[te]
group_te = true_group[te]

Dv0 = np.hstack([D, np.zeros((n, 1))])
Dv1 = np.hstack([D, np.ones((n, 1))])
D_full = np.hstack([D, v[:, None]])

preds = {f"{e}_{r}": [] for e in ESTIMATORS for r in RANKINGS}

for rep in range(R):
    rr = np.random.default_rng(SEED + rep)
    boot = rr.choice(tr_pool, size=len(tr_pool), replace=True)

    for e in ESTIMATORS:
        s = make(e).fit(D_full[boot], y[boot])
        p0 = s.predict_proba(Dv0[te])[:, 1]
        preds[f"{e}_risk"].append(p0)

        b0 = boot[v[boot] == 0]
        b1 = boot[v[boot] == 1]
        m0 = make(e).fit(D[b0], y[b0])
        m1 = make(e).fit(D[b1], y[b1])
        preds[f"{e}_effect"].append(
            m1.predict_proba(D_te)[:, 1] - m0.predict_proba(D_te)[:, 1]
        )

    print(f"  repeat {rep} done ({time.time() - t0:.0f}s)")

results = {}
for key, plist in preds.items():
    P = np.vstack(plist)
    rho = [float(spearmanr(P[i], P[j]).statistic) for i, j in combinations(range(R), 2)]
    entry = {
        "spearman_median": float(np.median(rho)),
        "spearman_min": float(np.min(rho)),
        "capacities": {},
    }
    for cap in CAPACITIES:
        k = max(1, int(round(cap * n_eval)))
        sets = [top_k(P[i], k) for i in range(R)]
        js = [jaccard(a, b) for a, b in combinations(sets, 2)]
        ssets = [set(s.tolist()) for s in sets]
        core = set.intersection(*ssets)
        union = set().union(*ssets)
        sums = np.array([P[i][sets[i]].sum() for i in range(R)])
        true_vals = np.array([tau_te[sets[i]].mean() for i in range(R)])
        harm = np.array([(tau_te[sets[i]] < 0).mean() for i in range(R)])
        entry["capacities"][f"{cap:.2f}"] = {
            "k": int(k),
            "jaccard_median": float(np.median(js)),
            "jaccard_min": float(np.min(js)),
            "core_frac_of_k": float(len(core) / k),
            "union_over_k": float(len(union) / k),
            "sum_mean": float(sums.mean()),
            "sum_cv": float(abs(sums.std(ddof=1) / sums.mean())),
            "true_effect_mean": float(true_vals.mean()),
            "true_effect_sd": float(true_vals.std(ddof=1)),
            "harm_share_mean": float(harm.mean()),
            "harm_share_sd": float(harm.std(ddof=1)),
        }
    results[key] = entry

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

cap_key = f"{HEADLINE_CAPACITY:.2f}"


def verdict(x):
    if x >= JACCARD_STABLE:
        return "stable"
    if x >= JACCARD_MARGINAL:
        return "marginal"
    return "not usable"


w("# 20. Advancement stability")
w()
w("Generated by `20_advancement_stability.py`. Do not edit by hand.")
w()
w(
    "Simulation. A fixed evaluation fold of "
    f"{n_eval:,} prospects is scored by models fitted on {R} bootstrap resamples of the "
    "training pool. The population never moves, so everything here is the model reacting "
    "to its training sample."
)
w()
w(
    "Two deployable rankings are measured, not one. The effect ranking is a difference "
    "between two estimated quantities and `19b` showed the observables explain under five "
    "percent of the variance in true effect, so it has little reason to be as reproducible "
    "as the risk ranking."
)
w()
w("## Pre registered thresholds")
w()
w("| Quantity | Stable | Marginal | Not usable |")
w("|---|---|---|---|")
w(f"| Median pairwise Jaccard | at or above {JACCARD_STABLE:.2f} | "
  f"{JACCARD_MARGINAL:.2f} to {JACCARD_STABLE:.2f} | below {JACCARD_MARGINAL:.2f} |")
w(f"| CV of summed selected score | at or below {CV_STABLE:.2f} | | above {CV_STABLE:.2f} |")
w()
w("Carried unchanged from the clinical domain. Not adjusted after seeing results.")
w()

w(f"## Ranking stability at the operational capacity")
w()
w(f"{HEADLINE_CAPACITY:.0%} of the evaluation fold, "
  f"{results['logit_risk']['capacities'][cap_key]['k']:,} prospects.")
w()
w("| Estimator | Ranking | Jaccard median | Jaccard worst | Verdict | Core | Union over k |")
w("|---|---|---:|---:|---|---:|---:|")
for e in ESTIMATORS:
    for r in RANKINGS:
        c = results[f"{e}_{r}"]["capacities"][cap_key]
        w(
            f"| {e} | {r} | {c['jaccard_median']:.3f} | {c['jaccard_min']:.3f} | "
            f"{verdict(c['jaccard_median'])} | {c['core_frac_of_k']:.3f} | "
            f"{c['union_over_k']:.3f} |"
        )
w()

w("## Stability across capacity")
w()
w("| Estimator | Ranking | " + " | ".join(f"{c:.0%}" for c in CAPACITIES) + " |")
w("|---|---|" + "---:|" * len(CAPACITIES))
for e in ESTIMATORS:
    for r in RANKINGS:
        vals = " | ".join(
            f"{results[f'{e}_{r}']['capacities'][f'{c:.2f}']['jaccard_median']:.3f}"
            for c in CAPACITIES
        )
        w(f"| {e} | {r} | {vals} |")
w()

w("## Estimate stability")
w()
w(
    "Summed selected score across repeats. For the risk ranking this is expected gifts in "
    "the portfolio. For the effect ranking it is expected incremental gifts, which is the "
    "number a shop would report to a board."
)
w()
w("| Estimator | Ranking | Mean sum | CV | Within threshold |")
w("|---|---|---:|---:|---|")
for e in ESTIMATORS:
    for r in RANKINGS:
        c = results[f"{e}_{r}"]["capacities"][cap_key]
        w(
            f"| {e} | {r} | {c['sum_mean']:,.1f} | {c['sum_cv']:.4f} | "
            f"{'yes' if c['sum_cv'] <= CV_STABLE else 'NO'} |"
        )
w()

w("## Consequence stability")
w()
w(
    "What the selected portfolio is actually worth, using the true effects `18` retained. "
    "A list that churns but delivers the same value is a different problem from a list "
    "that churns and delivers different value."
)
w()
w("| Estimator | Ranking | True effect mean | SD across repeats | Harm share mean | SD |")
w("|---|---|---:|---:|---:|---:|")
for e in ESTIMATORS:
    for r in RANKINGS:
        c = results[f"{e}_{r}"]["capacities"][cap_key]
        w(
            f"| {e} | {r} | {c['true_effect_mean']:+.4f} | {c['true_effect_sd']:.4f} | "
            f"{c['harm_share_mean']:.1%} | {c['harm_share_sd']:.1%} |"
        )
w()

w("## Rank agreement across the whole population")
w()
w(
    "Spearman sees the entire ordering. A high value alongside a low Jaccard means the "
    "ranking is broadly reproducible but the cut point falls in a crowded region."
)
w()
w("| Estimator | Ranking | Median | Worst |")
w("|---|---|---:|---:|")
for e in ESTIMATORS:
    for r in RANKINGS:
        x = results[f"{e}_{r}"]
        w(f"| {e} | {r} | {x['spearman_median']:.4f} | {x['spearman_min']:.4f} |")
w()

risk_best = max(ESTIMATORS, key=lambda e: results[f"{e}_risk"]["capacities"][cap_key]["jaccard_median"])
eff_best = max(ESTIMATORS, key=lambda e: results[f"{e}_effect"]["capacities"][cap_key]["jaccard_median"])
risk_j = results[f"{risk_best}_risk"]["capacities"][cap_key]["jaccard_median"]
eff_j = results[f"{eff_best}_effect"]["capacities"][cap_key]["jaccard_median"]

w("## Summary")
w()
w("| Quantity | Value |")
w("|---|---|")
w(f"| Best risk ranking | {risk_best} at {risk_j:.3f}, {verdict(risk_j)} |")
w(f"| Best effect ranking | {eff_best} at {eff_j:.3f}, {verdict(eff_j)} |")
w(f"| Gap | {risk_j - eff_j:+.3f} |")
w()
w(
    "If the effect ranking is materially less stable than the risk ranking, that is a cost "
    "of the alternative this project asks institutions to consider, and it belongs in the "
    "recommendation rather than in a footnote. `21` allocates using both and reports the "
    "value each delivers against the oracle."
)
w()

w("## Limitations")
w()
w(
    "Bootstrap resampling measures sensitivity to the training sample only. It does not "
    "measure sensitivity to feature choice, to the historical policy, or to the generator "
    "parameters, all of which are swept elsewhere. Gradient boosting is not bitwise "
    "deterministic across thread counts, so its rows may vary slightly between machines "
    "while logistic rows will not. All parameters remain illustrative and open in "
    "`08_sources.md`."
)
w()

stats["seed"] = SEED
stats["repeats"] = R
stats["eval_fold"] = EVAL_FOLD
stats["n_eval"] = n_eval
stats["capacities"] = CAPACITIES
stats["headline_capacity"] = HEADLINE_CAPACITY
stats["thresholds"] = {
    "jaccard_stable": JACCARD_STABLE,
    "jaccard_marginal": JACCARD_MARGINAL,
    "cv_stable": CV_STABLE,
}
stats["results"] = results
stats["summary"] = {
    "risk_best": risk_best, "risk_jaccard": risk_j,
    "effect_best": eff_best, "effect_jaccard": eff_j,
}
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "20_advancement_stability.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "advancement_stability_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.1f}s")
print("Wrote docs/20_advancement_stability.md")
print("Wrote cache/advancement_stability_stats.json")
