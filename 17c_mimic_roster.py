"""
17c_mimic_roster.py

Exports which patients each approach would enrol, and what happens to that list when the
same model is rebuilt on a slightly different sample.

WHY THIS EXISTS
===============
`15_mimic_stability.py` established the finding this domain is really about, and an
earlier version of this script stated it wrongly. The finding is not that every model
churns. It is that the two estimators behave completely differently, and the one that
wins on every accuracy measure is the one whose list cannot be reproduced.

    gradient boosting   better discrimination in all twelve configurations
    logistic regression more stable ranking in all twelve

A hospital choosing on accuracy alone picks the first. `15` reported that as summary
statistics, and a summary statistic cannot show a list changing. This script records the
actual lists for both estimators so the difference can be watched rather than asserted.

`17_mimic_allocation.py` compared risk ranking against effect ranking under an assumed
efficacy shape. Same thing: it reported overlap, not membership.

Neither script is modified and neither result changes. This reruns the same procedure on
one configuration and writes down who is selected.

ONE CONFIGURATION, CHOSEN BEFORE RESULTS
========================================
    at_discharge, regime A, 30 day window

Discharge because that is the decision point where enrolment can still change the stay.
Regime A because it makes no assumption about censored admissions. Thirty days because it
is the horizon the readmission literature uses. Chosen on those grounds before any number
from this script existed.

Logistic regression, as `15` established for this domain.

WHAT IS EXPORTED
================
    risk        ranked by predicted probability of readmission
    effect      ranked by an assumed benefit that falls away at the top of the risk
                distribution, the shape `17b` swept. Assumed, not measured. MIMIC contains
                no intervention and none is claimed.
    logit_rebuild_1..R    the logistic ranking refitted on bootstrap resamples
    boost_rebuild_1..R    the boosted ranking refitted on the same resamples

Both estimators see identical resamples and score identical patients. Nothing differs
between a pair of rebuilds except which admissions the model happened to learn from, and
nothing differs between the two families except the estimator. Alongside each, the summed
predicted probability of the selected slice is recorded, because that is the number a
programme would report upward.

Usage:
    python 17c_mimic_roster.py

Reads:
    data/processed/mimic_features_at_discharge.parquet

Writes:
    cache/clinical_roster.json
    docs/17c_mimic_roster.md
"""

import json
import time
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

POINT = "at_discharge"
REGIME = "A"
WINDOW = 30

SEED = 20260821
N_REBUILDS = 8
CAPACITIES = [0.01, 0.03, 0.05, 0.10, 0.20]
HEADLINE_CAPACITY = 0.05
ROSTER_N = 1200

# benefit falls away at the top of the risk distribution. Assumed, not measured.
BETA = 1.0

CATEGORICAL = [
    "gender", "admission_type", "admission_location", "insurance",
    "marital_status", "race", "service_grouped", "discharge_location",
]
DROP = ["subject_id", "hadm_id", "regime", "window", "readmit", "fold", "is_final"]
EQUITY = ["service_grouped", "insurance", "race", "discharge_location"]

lines = []


def w(s=""):
    lines.append(s)
    print(s)


def top_k(x, k):
    return np.argsort(-x, kind="stable")[:k]


def jac(a, b):
    a, b = set(a.tolist()), set(b.tolist())
    return len(a & b) / len(a | b) if (a | b) else float("nan")


def fit(Xtr, ytr, Xte, cats, nums):
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), cats),
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), nums),
    ])
    pipe = make_pipeline(pre, LogisticRegression(max_iter=1000, solver="lbfgs"))
    pipe.fit(Xtr, ytr)
    return pipe.predict_proba(Xte)[:, 1]


def fit_boosted(Xtr, ytr, Xte, mask):
    clf = HistGradientBoostingClassifier(
        categorical_features=mask, random_state=SEED,
        early_stopping=True, validation_fraction=0.15,
    )
    clf.fit(Xtr, ytr)
    return clf.predict_proba(Xte)[:, 1]


t0 = time.time()
tbl = pd.read_parquet(PROC / f"mimic_features_{POINT}.parquet")
s = tbl[(tbl["regime"] == REGIME) & (tbl["window"] == WINDOW)].reset_index(drop=True)
if len(s) == 0:
    raise SystemExit(f"No rows for {POINT} regime {REGIME} window {WINDOW}.")

feat = [c for c in s.columns if c not in DROP]
cats = [c for c in CATEGORICAL if c in feat]
nums = [c for c in feat if c not in cats]

X = s[feat].copy()
for c in cats:
    X[c] = X[c].astype("object").where(X[c].notna(), "__missing__")
Xe = X.copy()
if cats:
    Xe[cats] = OrdinalEncoder(
        handle_unknown="use_encoded_value", unknown_value=-1
    ).fit_transform(X[cats])
Xe = Xe.astype(float)
cat_mask = [c in cats for c in Xe.columns]

y = s["readmit"].to_numpy()
folds = s["fold"].to_numpy()

eval_fold = sorted(np.unique(folds))[-1]
te = folds == eval_fold
tr_pool = np.flatnonzero(folds != eval_fold)
n_eval = int(te.sum())
X_te, Xe_te = X[te], Xe[te]
y_te = y[te]
print(f"{len(s):,} admissions, {n_eval:,} held out for scoring")

# both estimators as built
p_risk = fit(X.iloc[tr_pool], y[tr_pool], X_te, cats, nums)
p_boost = fit_boosted(Xe.iloc[tr_pool], y[tr_pool], Xe_te, cat_mask)
auc = float(roc_auc_score(y_te, p_risk))
auc_boost = float(roc_auc_score(y_te, p_boost))
print(f"  logistic auc {auc:.3f}, boosted auc {auc_boost:.3f} ({time.time() - t0:.0f}s)")

# both rebuilt on identical resamples
logit_rebuilds, boost_rebuilds = [], []
for r in range(N_REBUILDS):
    rng = np.random.default_rng(SEED + r)
    boot = rng.choice(tr_pool, size=len(tr_pool), replace=True)
    logit_rebuilds.append(fit(X.iloc[boot], y[boot], X_te, cats, nums))
    boost_rebuilds.append(fit_boosted(Xe.iloc[boot], y[boot], Xe_te, cat_mask))
    print(f"  rebuild {r + 1} of {N_REBUILDS} ({time.time() - t0:.0f}s)")

# benefit assumed to fall away at the top of the risk distribution
p_effect = p_risk * (1.0 - p_risk) ** BETA

# Sampling is done per capacity and weighted toward the patients some approach
# selects. A uniform sample of 1,200 from 64,093 would put roughly twelve enrolled
# patients on screen at the 1% capacity, which shows nothing. The sampling fraction
# is recorded so the page can state what is being displayed.
SELECTED_SHARE = 0.75

names = (["risk", "effect", "boosted"]
         + [f"logit_rebuild_{i + 1}" for i in range(N_REBUILDS)]
         + [f"boost_rebuild_{i + 1}" for i in range(N_REBUILDS)])
scores = [p_risk, p_effect, p_boost] + logit_rebuilds + boost_rebuilds

caps = {}
orders = {}
for cap in CAPACITIES:
    k = max(1, int(round(cap * n_eval)))
    sel = {nm: top_k(sc, k) for nm, sc in zip(names, scores)}

    srng = np.random.default_rng(SEED + 555 + int(cap * 10000))
    in_any = np.zeros(n_eval, dtype=bool)
    for nm in names:
        in_any[sel[nm]] = True
    picked = np.flatnonzero(in_any)
    n_sel = min(len(picked), int(ROSTER_N * SELECTED_SHARE))
    take = srng.choice(picked, size=n_sel, replace=False)
    rest = np.flatnonzero(~in_any)
    n_rest = min(len(rest), ROSTER_N - n_sel)
    if n_rest > 0:
        take = np.concatenate([take, srng.choice(rest, size=n_rest, replace=False)])
    order = np.sort(take)
    orders[f"{cap:.2f}"] = order

    masks = []
    for j in order:
        bits = 0
        for bpos, nm in enumerate(names):
            if j in sel[nm]:
                bits |= (1 << bpos)
        masks.append(bits)

    def family(prefix, base):
        rb = [f"{prefix}_rebuild_{i + 1}" for i in range(N_REBUILDS)]
        pair = [jac(sel[a], sel[b]) for a, b in combinations(rb, 2)]
        totals = [float(base[sel[nm]].sum()) for nm in rb]
        union, core = set(), None
        for nm in rb:
            ss = set(sel[nm].tolist())
            union |= ss
            core = ss if core is None else (core & ss)
        return {
            "overlap_median": float(np.median(pair)),
            "overlap_min": float(np.min(pair)),
            "core_frac": float(len(core) / k),
            "union_over_k": float(len(union) / k),
            "reported_total_mean": float(np.mean(totals)),
            "reported_total_spread": float(
                (max(totals) - min(totals)) / np.mean(totals)
            ) if np.mean(totals) else float("nan"),
        }

    caps[f"{cap:.2f}"] = {
        "k": int(k),
        "n_eval": n_eval,
        "n_sampled": int(len(order)),
        "selected_in_sample": {nm: int(np.isin(order, sel[nm]).sum()) for nm in names},
        "mask": masks,
        "risk_vs_effect": float(jac(sel["risk"], sel["effect"])),
        "logit_vs_boosted": float(jac(sel["risk"], sel["boosted"])),
        "logit": family("logit", p_risk),
        "boosted": family("boost", p_boost),
    }

order = orders[f"{HEADLINE_CAPACITY:.2f}"]
eq = {}
for col in EQUITY:
    if col not in s.columns:
        continue
    vals = [
        "not recorded" if pd.isna(v) else str(v)
        for v in s[col].to_numpy()[te][order]
    ]
    levels = sorted(set(vals))
    if len(levels) <= 12:
        eq[col] = {"levels": levels, "index": [levels.index(v) for v in vals]}

roster = {
    "configuration": {
        "point": POINT, "regime": REGIME, "window": WINDOW,
        "auc_logistic": auc, "auc_boosted": auc_boost,
    },
    "lists": names,
    "list_labels": {
        "risk": "The steadier model",
        "effect": "Most likely to be helped",
        "boosted": "The more accurate model",
        **{f"logit_rebuild_{i + 1}": f"Steadier, rebuild {i + 1}" for i in range(N_REBUILDS)},
        **{f"boost_rebuild_{i + 1}": f"Accurate, rebuild {i + 1}" for i in range(N_REBUILDS)},
    },
    "families": {"logit": "logit_rebuild", "boosted": "boost_rebuild"},
    "n_rebuilds": N_REBUILDS,
    "capacities": CAPACITIES,
    "headline_capacity": HEADLINE_CAPACITY,
    "beta": BETA,
    "readmission_rate": float(y_te.mean()),
    # Per-patient insurance and discharge codes are not exported. They are restricted
    # data under the PhysioNet licence, and the page never reads them.
    "note": (
        "One configuration: at discharge, no assumption about censored admissions, thirty "
        "day horizon. Benefit is assumed to fall away at the top of the risk distribution; "
        "nobody in this data was randomised, so it cannot be measured. The rebuilds differ "
        "only in which admissions the model happened to learn from."
    ),
    "by_capacity": caps,
}
CACHE.mkdir(parents=True, exist_ok=True)
(CACHE / "clinical_roster.json").write_text(json.dumps(roster), encoding="utf-8")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

hk = f"{HEADLINE_CAPACITY:.2f}"

w("# 17c. Clinical roster")
w()
w("Generated by `17c_mimic_roster.py`. Do not edit by hand.")
w()
w(
    f"`{POINT}`, regime {REGIME}, {WINDOW} day window. {len(s):,} admissions, {n_eval:,} "
    "held out for scoring. Both estimators are run so the trade between accuracy and "
    "reproducibility can be seen directly. `15` and `17` are unmodified and their results "
    "do not change."
)
w()

w("## Accuracy against reproducibility")
w()
w(
    f"Two estimators, same admissions, same held out patients. Logistic AUC {auc:.3f}, "
    f"boosted AUC {auc_boost:.3f}. Each is rebuilt {N_REBUILDS} times on identical "
    "resamples of the training data."
)
w()
w("| Capacity | Enrolled | Steadier: two rebuilds share | Accurate: two rebuilds share | "
  "Steadier: distinct named | Accurate: distinct named |")
w("|---:|---:|---:|---:|---:|---:|")
for cap in CAPACITIES:
    c = caps[f"{cap:.2f}"]
    w(f"| {cap:.0%} | {c['k']:,} | {c['logit']['overlap_median']:.1%} | "
      f"{c['boosted']['overlap_median']:.1%} | {c['logit']['union_over_k']:.2f}x | "
      f"{c['boosted']['union_over_k']:.2f}x |")
w()
w(
    "Distinct named is how many different patients appear across all rebuilds, as a "
    "multiple of the places available. A hospital choosing on accuracy alone takes the "
    "boosted model. Whether its list can be produced twice is a separate question, and "
    "it is not asked by any standard accuracy measure."
)
w()
w("## What the reported number does while the list moves")
w()
w("| Capacity | Steadier: total spread | Accurate: total spread |")
w("|---:|---:|---:|")
for cap in CAPACITIES:
    c = caps[f"{cap:.2f}"]
    w(f"| {cap:.0%} | {c['logit']['reported_total_spread']:.1%} | "
      f"{c['boosted']['reported_total_spread']:.1%} |")
w()
w(
    "The spread is how much the figure a programme would send upward moves between "
    "rebuilds. Where it is small and the list is not, the number on the report is steady "
    "while the people receiving care are not."
)
w()
w("## Do the two estimators pick the same patients?")
w()
w("| Capacity | Overlap |")
w("|---:|---:|")
for cap in CAPACITIES:
    w(f"| {cap:.0%} | {caps[f'{cap:.2f}']['logit_vs_boosted']:.1%} |")
w()

w("## Risk against effect")
w()
w(
    f"Benefit assumed to fall away at the top of the risk distribution, beta {BETA:.1f}. "
    "Assumed, not measured."
)
w()
w("| Capacity | Overlap |")
w("|---:|---:|")
for cap in CAPACITIES:
    w(f"| {cap:.0%} | {caps[f'{cap:.2f}']['risk_vs_effect']:.1%} |")
w()

w("## Limitations")
w()
w(
    "One configuration of the twelve in `17`, chosen on clinical grounds before results "
    "existed. Nobody in this data was randomised, so who benefits is assumed and swept "
    "elsewhere rather than measured here. One hospital."
)
w()

DOCS.mkdir(parents=True, exist_ok=True)
(DOCS / "17c_mimic_roster.md").write_text("\n".join(lines), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.0f}s")
print("Wrote cache/clinical_roster.json")
print("Wrote docs/17c_mimic_roster.md")
