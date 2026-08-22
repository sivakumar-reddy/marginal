"""
15_mimic_stability.py

Establishes which estimator the MIMIC allocation step should use.

`14_mimic_risk_model.py` found HistGradientBoosting better than logistic on both Brier
and AUC in all twelve grid cells. That is not sufficient to choose it. The allocation
step does not consume a Brier score. It consumes an ordering, takes the top k of it under
a capacity constraint, and sums predicted probabilities inside that slice. What matters is
whether the identity of that slice survives a change in the training sample. A model can
rank better on average and still churn its top decile from one resample to the next, and a
director who reruns the list next quarter and finds half the names replaced has learned
that the tool is noise.

This is the same reasoning `07_stability.md` applied to OULAD, on this data rather than
inherited from it.

WHAT IS PERTURBED
=================
The evaluation population is fixed: one held out fold, identical across every repeat, so
that any movement in the ranking comes from the model rather than from the population.
The training pool is the remaining folds, bootstrap resampled with replacement R times.
Each resample produces a fitted model, which scores the same fixed evaluation set.

This isolates sensitivity to the training sample. It does not measure sensitivity to
feature choice, to the censoring regime, or to the window, all of which are carried as
explicit grid dimensions elsewhere and are not stability questions.

PRE REGISTERED THRESHOLDS
=========================
Stated here before the numbers exist, so that the reading cannot be fitted to the result.

    Ranking stability, measured as median pairwise Jaccard overlap of the top decile
    across repeats:

        at or above 0.80    stable enough for allocation
        0.60 to 0.80        marginal, usable only with the churn reported alongside it
        below 0.60          not usable, the list would not survive being rerun

    Estimate stability, measured as coefficient of variation of the summed predicted
    probability inside the top decile:

        at or below 0.02    the outcomes averted figure is reproducible
        above 0.02          the figure moves more than the effect sizes it is compared to

The second threshold matters because the allocation comparison turns on differences
between ranking strategies that are themselves small. An estimate that moves by more than
those differences under resampling cannot adjudicate between them.

WHAT THIS DOES NOT ESTABLISH
============================
Not leave one service out. MED is 51.73% of admissions and every number here is within
fold, so all of it overstates what a model achieves on a service it has never seen. That
is `16_mimic_validation.py`.

Not calibration under resampling. `14` established calibration on the full out of fold
predictions. Whether calibration itself is stable is a separate question and is not
answered here.

Not hyperparameter sensitivity. Defaults throughout, as in `14`.

RUNTIME
=======
    12 grid cells  x  2 estimators  x  R repeats

At R = 10 that is 240 fits against the 120 in `14`, on training pools of roughly four
fifths the size. Expect twelve to eighteen minutes. Progress prints per cell.

Usage:
    python 15_mimic_stability.py

Reads:
    data/processed/mimic_features_at_admission.parquet
    data/processed/mimic_features_at_discharge.parquet

Writes:
    docs/15_mimic_stability.md
    cache/mimic_stability_stats.json
"""

import json
import time
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

POINTS = ["at_admission", "at_discharge"]
REGIMES = ["A", "B", "C"]
WINDOWS = [30, 90]
ESTIMATORS = ["hgb", "logit"]

R = 10
CAPACITIES = [0.01, 0.05, 0.10, 0.20]
HEADLINE_CAPACITY = 0.10

JACCARD_STABLE = 0.80
JACCARD_MARGINAL = 0.60
CV_STABLE = 0.02

SEED = 20260821

CATEGORICAL = [
    "gender", "admission_type", "admission_location", "insurance",
    "marital_status", "race", "service_grouped", "discharge_location",
]
DROP = ["subject_id", "hadm_id", "regime", "window", "readmit", "fold", "is_final"]

stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


def top_k_set(scores, k):
    return set(np.argsort(-scores, kind="stable")[:k].tolist())


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a | b) else np.nan


def fit_hgb(Xtr, ytr, Xte, mask, seed):
    clf = HistGradientBoostingClassifier(
        categorical_features=mask, random_state=seed,
        early_stopping=True, validation_fraction=0.15,
    )
    clf.fit(Xtr, ytr)
    return clf.predict_proba(Xte)[:, 1]


def fit_logit(Xtr, ytr, Xte, cats, nums):
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), cats),
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), nums),
    ])
    pipe = make_pipeline(pre, LogisticRegression(max_iter=1000, solver="lbfgs"))
    pipe.fit(Xtr, ytr)
    return pipe.predict_proba(Xte)[:, 1]


w("# 15. MIMIC stability")
w()
w("Generated by `15_mimic_stability.py`. Do not edit by hand.")
w()
w(
    f"A fixed held out evaluation fold is scored by models fitted on {R} bootstrap "
    "resamples of the training pool. The population does not move, so everything measured "
    "here is the model reacting to its training sample."
)
w()
w("## Pre registered thresholds")
w()
w("| Quantity | Stable | Marginal | Not usable |")
w("|---|---|---|---|")
w(f"| Median pairwise Jaccard, top decile | at or above {JACCARD_STABLE:.2f} | "
  f"{JACCARD_MARGINAL:.2f} to {JACCARD_STABLE:.2f} | below {JACCARD_MARGINAL:.2f} |")
w(f"| CV of summed probability, top decile | at or below {CV_STABLE:.2f} | | "
  f"above {CV_STABLE:.2f} |")
w()
w(
    "These were fixed before the script was run. `14` reported that gradient boosting "
    "wins on discrimination in all twelve cells. That result has no vote here."
)
w()

results = {}
t0 = time.time()

for point in POINTS:
    tbl = pd.read_parquet(PROC / f"mimic_features_{point}.parquet")
    feat_cols = [c for c in tbl.columns if c not in DROP]
    cats = [c for c in CATEGORICAL if c in feat_cols]
    nums = [c for c in feat_cols if c not in cats]

    for regime in REGIMES:
        for wd in WINDOWS:
            s = tbl[(tbl["regime"] == regime) & (tbl["window"] == wd)].reset_index(drop=True)
            y = s["readmit"].to_numpy()
            folds = s["fold"].to_numpy()

            eval_fold = sorted(np.unique(folds))[-1]
            te = folds == eval_fold
            tr_pool = np.flatnonzero(folds != eval_fold)
            n_eval = int(te.sum())

            X = s[feat_cols].copy()
            for c in cats:
                X[c] = X[c].astype("object").where(X[c].notna(), "__missing__")
            Xe = X.copy()
            if cats:
                Xe[cats] = OrdinalEncoder(
                    handle_unknown="use_encoded_value", unknown_value=-1
                ).fit_transform(X[cats])
            Xe = Xe.astype(float)
            mask = [c in cats for c in Xe.columns]

            X_te, Xe_te = X[te], Xe[te]
            preds = {m: [] for m in ESTIMATORS}

            for r in range(R):
                rng = np.random.default_rng(SEED + r)
                boot = rng.choice(tr_pool, size=len(tr_pool), replace=True)
                preds["hgb"].append(fit_hgb(Xe.iloc[boot], y[boot], Xe_te, mask, SEED + r))
                preds["logit"].append(fit_logit(X.iloc[boot], y[boot], X_te, cats, nums))

            key = f"{point}_{regime}_{wd}"
            cell = {"point": point, "regime": regime, "window": wd, "n_eval": n_eval}

            for m in ESTIMATORS:
                P = np.vstack(preds[m])
                entry = {"capacities": {}}

                rho = [
                    float(spearmanr(P[i], P[j]).statistic)
                    for i, j in combinations(range(R), 2)
                ]
                entry["spearman_median"] = float(np.median(rho))
                entry["spearman_min"] = float(np.min(rho))

                for cap in CAPACITIES:
                    k = max(1, int(round(cap * n_eval)))
                    sets = [top_k_set(P[i], k) for i in range(R)]
                    js = [jaccard(a, b) for a, b in combinations(sets, 2)]

                    union = set().union(*sets)
                    core = set.intersection(*sets)
                    sums = np.array([P[i][sorted(sets[i])].sum() for i in range(R)])

                    entry["capacities"][f"{cap:.2f}"] = {
                        "k": k,
                        "jaccard_median": float(np.median(js)),
                        "jaccard_min": float(np.min(js)),
                        "core_frac_of_k": float(len(core) / k),
                        "union_over_k": float(len(union) / k),
                        "sum_mean": float(sums.mean()),
                        "sum_cv": float(sums.std(ddof=1) / sums.mean()),
                    }

                cell[m] = entry

            results[key] = cell
            print(f"  done {key}  ({time.time() - t0:.0f}s elapsed)")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

cap_key = f"{HEADLINE_CAPACITY:.2f}"

w("## Ranking stability at the headline capacity")
w()
w(f"Top decile of the evaluation fold. Jaccard is pairwise across the {R} repeats.")
w()
w("| Point | Regime | Window | k | HGB median | HGB worst | Logit median | Logit worst |")
w("|---|---|---:|---:|---:|---:|---:|---:|")
for k, r in results.items():
    h = r["hgb"]["capacities"][cap_key]
    l = r["logit"]["capacities"][cap_key]
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | {h['k']:,} | "
        f"{h['jaccard_median']:.3f} | {h['jaccard_min']:.3f} | "
        f"{l['jaccard_median']:.3f} | {l['jaccard_min']:.3f} |"
    )
w()

w("## Verdict against the pre registered thresholds")
w()
w("| Point | Regime | Window | HGB | Logit |")
w("|---|---|---:|---|---|")


def verdict(v):
    if v >= JACCARD_STABLE:
        return "stable"
    if v >= JACCARD_MARGINAL:
        return "marginal"
    return "not usable"


for k, r in results.items():
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | "
        f"{verdict(r['hgb']['capacities'][cap_key]['jaccard_median'])} | "
        f"{verdict(r['logit']['capacities'][cap_key]['jaccard_median'])} |"
    )
w()

w("## How stability moves with capacity")
w()
w(
    "A tighter capacity is a harder stability problem. The top one percent is the slice a "
    "constrained programme would actually reach, and it is the slice most exposed to "
    "resampling."
)
w()
w("| Point | Regime | Window | Estimator | 1% | 5% | 10% | 20% |")
w("|---|---|---:|---|---:|---:|---:|---:|")
for k, r in results.items():
    for m in ESTIMATORS:
        vals = " | ".join(
            f"{r[m]['capacities'][f'{c:.2f}']['jaccard_median']:.3f}" for c in CAPACITIES
        )
        w(f"| {r['point']} | {r['regime']} | {r['window']} | {m} | {vals} |")
w()

w("## Churn and core")
w()
w(
    "Core is the fraction of one list that appears in every repeat. Union over k is how "
    "many distinct people were named across all repeats, expressed as a multiple of the "
    "capacity. A union of 1.6 means the programme would have to contact sixty percent "
    "more people than it has room for to cover everyone any repeat selected."
)
w()
w("| Point | Regime | Window | Estimator | Core | Union over k |")
w("|---|---|---:|---|---:|---:|")
for k, r in results.items():
    for m in ESTIMATORS:
        c = r[m]["capacities"][cap_key]
        w(
            f"| {r['point']} | {r['regime']} | {r['window']} | {m} | "
            f"{c['core_frac_of_k']:.3f} | {c['union_over_k']:.3f} |"
        )
w()

w("## Estimate stability")
w()
w(
    "Summed predicted probability inside the top decile, which is the quantity the "
    "allocation step reports as outcomes averted before any efficacy assumption is "
    "applied."
)
w()
w("| Point | Regime | Window | Estimator | Mean sum | CV | Within threshold |")
w("|---|---|---:|---|---:|---:|---|")
for k, r in results.items():
    for m in ESTIMATORS:
        c = r[m]["capacities"][cap_key]
        w(
            f"| {r['point']} | {r['regime']} | {r['window']} | {m} | "
            f"{c['sum_mean']:,.1f} | {c['sum_cv']:.4f} | "
            f"{'yes' if c['sum_cv'] <= CV_STABLE else 'NO'} |"
        )
w()

w("## Rank agreement across the whole population")
w()
w(
    "Jaccard sees only the boundary of the selected slice. Spearman sees the whole "
    "ordering, and a high value alongside a low Jaccard means the ranking is broadly "
    "reproducible but the cut point falls in a crowded region where small movements "
    "reshuffle membership."
)
w()
w("| Point | Regime | Window | HGB median | HGB worst | Logit median | Logit worst |")
w("|---|---|---:|---:|---:|---:|---:|")
for k, r in results.items():
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | "
        f"{r['hgb']['spearman_median']:.4f} | {r['hgb']['spearman_min']:.4f} | "
        f"{r['logit']['spearman_median']:.4f} | {r['logit']['spearman_min']:.4f} |"
    )
w()

# ---------------------------------------------------------------------------
# Which estimator carries forward
# ---------------------------------------------------------------------------

hgb_wins = sum(
    1 for r in results.values()
    if r["hgb"]["capacities"][cap_key]["jaccard_median"]
    > r["logit"]["capacities"][cap_key]["jaccard_median"]
)
n_cells = len(results)
hgb_pass = sum(
    1 for r in results.values()
    if r["hgb"]["capacities"][cap_key]["jaccard_median"] >= JACCARD_STABLE
)
logit_pass = sum(
    1 for r in results.values()
    if r["logit"]["capacities"][cap_key]["jaccard_median"] >= JACCARD_STABLE
)

w("## Which estimator carries forward")
w()
w(f"Gradient boosting is the more stable of the two in {hgb_wins} of {n_cells} cells.")
w(f"Cells clearing the stable threshold: gradient boosting {hgb_pass}, logistic {logit_pass}.")
w()
w(
    "`14` established that gradient boosting discriminates better in every cell. If it is "
    "also the more stable here, the choice is unambiguous and the education domain's "
    "preference for logistic simply does not transfer, which is the outcome that justifies "
    "having measured rather than inherited. If the two disagree, stability governs, "
    "because the allocation comparison is a comparison of who gets selected and an "
    "unstable selection cannot support it."
)
w()

stats["results"] = results
stats["seed"] = SEED
stats["repeats"] = R
stats["thresholds"] = {
    "jaccard_stable": JACCARD_STABLE,
    "jaccard_marginal": JACCARD_MARGINAL,
    "cv_stable": CV_STABLE,
}
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "15_mimic_stability.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "mimic_stability_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.0f}s")
print("Wrote docs/15_mimic_stability.md")
print("Wrote cache/mimic_stability_stats.json")
