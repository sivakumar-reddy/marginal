"""
07_stability.py  (version 2)

Measures whether two risk models built on different historical data produce the same
priority list for the same students.

WHY THIS WAS REWRITTEN
======================
Version 1 fit each model on a bootstrap resample and then predicted on the entire
cohort, including the rows it had trained on. A bootstrap sample contains roughly 63% of
unique rows, so most predictions were in sample. Gradient boosting memorised them: AUC
came out at 0.926 and 0.952 against an honest cross validated estimate of 0.69 to 0.71.
The measured disagreement was therefore memorisation noise, not ranking instability. The
logistic model, which lacks the capacity to memorise, scored 0.676 and showed far higher
agreement, which is what exposed the error.

The noise floor in `06_allocation.md` was produced the same way and is invalid. It must
be replaced by the figures here before any claim in 06 is reported.

THE DESIGN NOW
==============
Each cohort is split three ways at student level:

    part A   trains model A
    part B   trains model B
    part C   evaluation, seen by neither

Both models rank part C. Their top k sets are compared. This is the question an
institution actually faces: two years of history, two different training sets, does the
call list come out the same. Discrimination is measured on part C as well, so an
inflated AUC would be visible immediately rather than silently driving the result.

Three estimators are compared, since instability could be a property of the estimator
rather than the problem:

    single      one HistGradientBoosting fit
    bagged      mean over BAG_SIZE fits on resamples of the training part
    logistic    L2 logistic regression, higher bias, much lower variance

A ceiling is also reported: two gradient boosting models trained on the SAME data with
different random seeds. Any disagreement there is algorithmic nondeterminism in that
estimator alone. It bounds what gradient boosting could achieve; it does not bound the
logistic model, which is close to deterministic given its training data and whose own
ceiling would be near 1.0.

Usage:
    python 07_stability.py

Reads:
    data/processed/features_d{D}.parquet

Writes:
    docs/07_stability.md
    cache/stability_stats.json
"""

import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

DAYS = [0, 28]
CAPACITY_PCT = [0.01, 0.02, 0.05, 0.10, 0.20]
N_REPLICATIONS = 10
BAG_SIZE = 15
MIN_COHORT = 1500
SEED = 20260821

CATEGORICAL = ["gender", "region", "highest_education", "imd_band", "age_band", "disability"]
DROP = ["id_student", "fold", "outcome", "code_module", "code_presentation"]

def seed_for(*parts):
    """Deterministic seed from labels. Independent of loop order, so figures reproduce
    exactly on rerun and do not shift when a day or cohort is added or removed."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big")


stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


def topk(x, k):
    idx = np.argsort(-x, kind="stable")[:k]
    m = np.zeros(len(x), dtype=bool)
    m[idx] = True
    return m


def encode_hgb(X, cats):
    Xe = X.copy()
    for c in cats:
        Xe[c] = Xe[c].astype("object").where(Xe[c].notna(), "__missing__")
    if cats:
        Xe[cats] = OrdinalEncoder(
            handle_unknown="use_encoded_value", unknown_value=-1
        ).fit_transform(Xe[cats])
    return Xe.astype(float), [c in cats for c in Xe.columns]


def hgb(Xtr, ytr, Xte, mask, seed):
    clf = HistGradientBoostingClassifier(
        categorical_features=mask, random_state=seed, early_stopping=True, validation_fraction=0.15
    )
    clf.fit(Xtr, ytr)
    return clf.predict_proba(Xte)[:, 1]


def hgb_bagged(Xtr, ytr, Xte, mask, seed, bag, gen):
    n = len(Xtr)
    out = np.zeros(len(Xte))
    for b in range(bag):
        idx = gen.integers(0, n, n)
        out += hgb(Xtr.iloc[idx], ytr[idx], Xte, mask, seed + b)
    return out / bag


def logit(Xtr, ytr, Xte, cats, nums):
    pre = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), cats),
            ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), nums),
        ]
    )
    pipe = make_pipeline(pre, LogisticRegression(max_iter=2000))
    pipe.fit(Xtr, ytr)
    return pipe.predict_proba(Xte)[:, 1]


w("# 07. Ranking stability")
w()
w("Generated by `07_stability.py`. Do not edit by hand.")
w()
w("## Correction")
w()
w(
    "The first version of this analysis fit each model on a bootstrap resample and then "
    "predicted on the whole cohort, including rows it had trained on. Gradient boosting "
    "memorised those rows and reported AUC of 0.926 and 0.952 against an honest cross "
    "validated estimate near 0.70. The disagreement it measured was memorisation noise. "
    "The noise floor in `06_allocation.md` was produced the same way and is invalid. "
    "The figures below replace it."
)
w()
w(
    "Each cohort is split three ways at student level. Model A trains on part A, model B "
    "on part B, and both rank part C, which neither has seen. Discrimination is reported "
    "on part C so that any inflation is visible."
)
w()
w(
    f"{N_REPLICATIONS} replications per estimator. The ceiling row is two gradient "
    "boosting models trained on identical data with different seeds. It bounds gradient "
    "boosting only. Logistic regression is close to deterministic given its training "
    "data, so its own ceiling would be near 1.0 and is not shown."
)
w()

results = {}

for D in DAYS:
    feat = pd.read_parquet(PROC / f"features_d{D}.parquet")
    sizes = feat.groupby(["code_module", "code_presentation"]).size()
    mp = sizes[sizes >= MIN_COHORT].idxmax()
    sub = feat[(feat["code_module"] == mp[0]) & (feat["code_presentation"] == mp[1])].reset_index(
        drop=True
    )

    cols = [c for c in sub.columns if c not in DROP]
    cats = [c for c in CATEGORICAL if c in cols]
    nums = [c for c in cols if c not in cats]
    X = sub[cols]
    y = sub["outcome"].to_numpy()
    Xe, mask = encode_hgb(X, cats)
    n = len(sub)

    methods = ("single", "bagged", "logistic", "ceiling")
    per = {m: {f"{p:.2f}": [] for p in CAPACITY_PCT} for m in methods}
    aucs = {m: [] for m in methods}

    for rep in range(N_REPLICATIONS):
        rng = np.random.default_rng(seed_for(SEED, D, mp[0], mp[1], rep))
        perm = rng.permutation(n)
        a, b, c = np.array_split(perm, 3)
        s = seed_for(SEED, D, mp[0], mp[1], rep, "model") % (2**31)

        preds = {
            "single": (
                hgb(Xe.iloc[a], y[a], Xe.iloc[c], mask, s),
                hgb(Xe.iloc[b], y[b], Xe.iloc[c], mask, s + 1),
            ),
            "bagged": (
                hgb_bagged(Xe.iloc[a], y[a], Xe.iloc[c], mask, s, BAG_SIZE, rng),
                hgb_bagged(Xe.iloc[b], y[b], Xe.iloc[c], mask, s + 500, BAG_SIZE, rng),
            ),
            "logistic": (
                logit(X.iloc[a], y[a], X.iloc[c], cats, nums),
                logit(X.iloc[b], y[b], X.iloc[c], cats, nums),
            ),
            "ceiling": (
                hgb(Xe.iloc[a], y[a], Xe.iloc[c], mask, s + 10),
                hgb(Xe.iloc[a], y[a], Xe.iloc[c], mask, s + 11),
            ),
        }

        yc = y[c]
        for m, (pa, pb) in preds.items():
            if 0 < yc.sum() < len(yc):
                aucs[m].append(roc_auc_score(yc, (pa + pb) / 2))
            for p in CAPACITY_PCT:
                k = max(1, int(round(p * len(c))))
                per[m][f"{p:.2f}"].append((topk(pa, k) & topk(pb, k)).sum() / k)

    full = hgb_bagged(
        Xe, y, Xe, mask, SEED, 5, np.random.default_rng(seed_for(SEED, D, "spread"))
    )
    top = np.sort(full)[::-1][: max(1, int(0.10 * n))]

    results[str(D)] = {
        "cohort": f"{mp[0]} {mp[1]}",
        "n": int(n),
        "n_eval": int(len(c)),
        "overlap": {
            m: {
                k2: {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1))}
                for k2, v in d.items()
            }
            for m, d in per.items()
        },
        "auc": {m: (float(np.mean(v)) if v else None) for m, v in aucs.items()},
        "top_decile_iqr": float(np.percentile(top, 75) - np.percentile(top, 25)),
        "top_decile_median": float(np.median(top)),
    }

for D in DAYS:
    r = results[str(D)]
    w(f"## Day {D}, cohort {r['cohort']}, N = {r['n']:,}, evaluation part = {r['n_eval']:,}")
    w()
    w("| Estimator | " + " | ".join(f"{p:.0%}" for p in CAPACITY_PCT) + " | AUC on part C |")
    w("|---|" + "---:|" * (len(CAPACITY_PCT) + 1))
    for m in ("single", "bagged", "logistic", "ceiling"):
        cells = " | ".join(f"{r['overlap'][m][f'{p:.2f}']['mean']:.2f}" for p in CAPACITY_PCT)
        auc = r["auc"][m]
        w(f"| {m} | {cells} | {auc:.3f} |" if auc else f"| {m} | {cells} | |")
    w()
    w(
        f"Top decile predicted risk: median {r['top_decile_median']:.3f}, "
        f"interquartile range {r['top_decile_iqr']:.3f}."
    )
    w()

w("## How to read this")
w()
w(
    "AUC on part C should sit near the cross validated figures in `04_risk_model.md`. If "
    "it does, the measurement is honest and the overlap numbers can be trusted."
)
w()
w(
    "The ceiling row bounds gradient boosting. Where a gradient boosting figure sits "
    "below it, the shortfall is caused by the training data differing, which is the real "
    "world condition. Where logistic exceeds the ceiling, that is not a contradiction: "
    "logistic has almost no seed dependence, so the gradient boosting ceiling says "
    "nothing about it."
)
w()
w(
    "Whichever estimator is most stable here is the one `06_allocation.py` should use, "
    "and its agreement figures are the noise floor against which the risk versus effect "
    "divergence must be judged."
)
w()

stats["results"] = results
stats["n_replications"] = N_REPLICATIONS
stats["bag_size"] = BAG_SIZE
stats["seed"] = SEED

(DOCS / "07_stability.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "stability_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print("Wrote docs/07_stability.md")
print("Wrote cache/stability_stats.json")
