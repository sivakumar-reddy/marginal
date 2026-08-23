"""
16_mimic_validation.py

Every number in `14` and `15` is within fold. Folds were drawn at random across the whole
population, so a model scored on fold five has almost certainly seen thousands of
admissions from the same clinical service, often the same patients on other visits. MED
alone is 51.73% of admissions. A within fold AUC therefore answers a question no hospital
asks, because the deployment question is whether the model works on a service, a unit or
a population it was not fitted on.

`15` established that logistic regression is the estimator the allocation step can use.
This script asks whether that model survives being moved.

THE MATCHED CONTROL
===================
A naive leave one service out design confounds two things. Holding out MED removes an
unseen service AND removes half the training data. A drop in performance could be either.

So each service is tested twice, on the same held out patients, with training sets of
identical size:

    Held out service S is split in half, A and B, at random. B is the test set in both
    arms and is never trained on.

    LOSO arm      trains on every row not in S.
    Control arm   trains on the same number of rows, of which half A is included and a
                  matching number of non S rows is dropped to keep the size equal.

The two arms differ in exactly one thing: whether the service being predicted is
represented in training. Training set size, test set, outcome definition and features are
identical. The difference between them is the transfer penalty and nothing else.

`service_grouped` is dropped from the feature set in both arms. It is constant in the
test set and unseen in LOSO training, and leaving it in would make the arms incomparable.

PRE REGISTERED THRESHOLDS
=========================
Fixed before the script was run.

    Ranking transfers if capture at the ten percent capacity under LOSO is within 0.02
    of the control arm. Capture is the share of all events in the test set that fall in
    the selected slice, which is what a capacity constrained programme actually gets.

    Level transfers if the absolute difference between mean predicted probability and
    observed rate on the held out service is at or below 0.02. If it is not, the model
    ranks correctly inside the service but reports the wrong magnitude, and the
    allocation step would need per service recalibration before pooling across services.

These can fail independently and the distinction matters. Ranking is what allocation
needs inside one service. Level is what it needs to compare services against each other.

WHAT THIS DOES NOT ESTABLISH
============================
Not transfer to another hospital. MIMIC is one academic medical center and every service
here shares its coding practice, its case mix and its documentation habits. A service is
the strongest held out population available in this data, and it is still weaker than the
question a director would ask.

Not temporal transfer. Nothing here holds out a later time period.

Not gradient boosting across the full grid. `15` settled the estimator, so logistic is
validated everywhere and gradient boosting is run as a spot check on regime A only, to
establish whether the transfer penalty is a property of the estimator or of the data.

RUNTIME
=======
    12 cells x S services x 2 arms, logistic
    plus 4 cells x S services x 2 arms, gradient boosting spot check

With six qualifying services that is roughly 190 fits. Expect fifteen to twenty five
minutes. Progress prints per cell.

Usage:
    python 16_mimic_validation.py

Reads:
    data/processed/mimic_features_at_admission.parquet
    data/processed/mimic_features_at_discharge.parquet

Writes:
    docs/16_mimic_validation.md
    cache/mimic_validation_stats.json
"""

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
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

HGB_SPOTCHECK_REGIMES = ["A"]

CAPACITIES = [0.01, 0.05, 0.10, 0.20]
HEADLINE_CAPACITY = 0.10

MIN_SERVICE_N = 5000
MIN_SERVICE_EVENTS = 500

CAPTURE_TOLERANCE = 0.02
LEVEL_TOLERANCE = 0.02

N_BINS = 10
SEED = 20260821

SERVICE_COL = "service_grouped"
CATEGORICAL = [
    "gender", "admission_type", "admission_location", "insurance",
    "marital_status", "race", "discharge_location",
]
DROP = ["subject_id", "hadm_id", "regime", "window", "readmit", "fold", "is_final", SERVICE_COL]

stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


def ece(y, p, n_bins=N_BINS):
    order = np.argsort(p)
    y, p = np.asarray(y)[order], np.asarray(p)[order]
    total, err = 0, 0.0
    for b in np.array_split(np.arange(len(y)), n_bins):
        if len(b) == 0:
            continue
        err += len(b) * abs(p[b].mean() - y[b].mean())
        total += len(b)
    return err / total if total else np.nan


def capture(y, p, cap):
    k = max(1, int(round(cap * len(p))))
    sel = np.argsort(-p, kind="stable")[:k]
    total = y.sum()
    return float(y[sel].sum() / total) if total else np.nan


def fit_logit(Xtr, ytr, Xte, cats, nums):
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), cats),
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), nums),
    ])
    pipe = make_pipeline(pre, LogisticRegression(max_iter=1000, solver="lbfgs"))
    pipe.fit(Xtr, ytr)
    return pipe.predict_proba(Xte)[:, 1]


def fit_hgb(Xtr, ytr, Xte, mask):
    clf = HistGradientBoostingClassifier(
        categorical_features=mask, random_state=SEED,
        early_stopping=True, validation_fraction=0.15,
    )
    clf.fit(Xtr, ytr)
    return clf.predict_proba(Xte)[:, 1]


def score(y, p):
    return {
        "auc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "ece": float(ece(y, p)),
        "mean_pred": float(p.mean()),
        "observed": float(y.mean()),
        "capture": {f"{c:.2f}": capture(y, p, c) for c in CAPACITIES},
    }


w("# 16. MIMIC validation on an unseen service")
w()
w("Generated by `16_mimic_validation.py`. Do not edit by hand.")
w()
w(
    "Everything in `14` and `15` is within fold, on folds drawn at random across a "
    "population where one service is more than half the rows. This script holds out a "
    "service and compares against a control arm trained on the same number of rows with "
    "that service represented, so the size of the training set cannot explain the "
    "difference."
)
w()
w("## Pre registered thresholds")
w()
w("| Quantity | Transfers if |")
w("|---|---|")
w(f"| Capture at the {HEADLINE_CAPACITY:.0%} capacity | LOSO within {CAPTURE_TOLERANCE:.2f} of control |")
w(f"| Calibration in the large | mean predicted minus observed at or below {LEVEL_TOLERANCE:.2f} |")
w()
w(
    "Ranking and level can fail independently. Ranking is what the allocation step needs "
    "inside one service. Level is what it needs to compare services against each other."
)
w()

results = {}
composition = {}
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
            svc_all = s[SERVICE_COL].astype(str).to_numpy()

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

            qualifying = []
            for svc in sorted(set(svc_all)):
                idx = np.flatnonzero(svc_all == svc)
                if len(idx) >= MIN_SERVICE_N and y[idx].sum() >= MIN_SERVICE_EVENTS:
                    qualifying.append(svc)
                composition.setdefault(f"{point}_{regime}_{wd}", []).append({
                    "service": svc,
                    "n": int(len(idx)),
                    "base_rate": float(y[idx].mean()),
                    "qualifies": bool(
                        len(idx) >= MIN_SERVICE_N and y[idx].sum() >= MIN_SERVICE_EVENTS
                    ),
                })

            run_hgb = regime in HGB_SPOTCHECK_REGIMES

            for svc in qualifying:
                rng = np.random.default_rng(SEED)
                idx_s = np.flatnonzero(svc_all == svc)
                rng.shuffle(idx_s)
                half = len(idx_s) // 2
                half_a, half_b = idx_s[:half], idx_s[half:]
                non_s = np.flatnonzero(svc_all != svc)

                loso_tr = non_s
                keep = rng.choice(non_s, size=len(non_s) - len(half_a), replace=False)
                ctrl_tr = np.concatenate([keep, half_a])
                assert len(loso_tr) == len(ctrl_tr), "training arms must be size matched"
                assert not set(half_b) & set(ctrl_tr), "test rows must not appear in training"

                y_te = y[half_b]
                key = f"{point}_{regime}_{wd}_{svc}"
                entry = {
                    "point": point, "regime": regime, "window": wd, "service": svc,
                    "n_service": int(len(idx_s)), "n_test": int(len(half_b)),
                    "n_train": int(len(loso_tr)),
                }

                p_loso = fit_logit(X.iloc[loso_tr], y[loso_tr], X.iloc[half_b], cats, nums)
                p_ctrl = fit_logit(X.iloc[ctrl_tr], y[ctrl_tr], X.iloc[half_b], cats, nums)
                entry["logit"] = {"loso": score(y_te, p_loso), "control": score(y_te, p_ctrl)}

                if run_hgb:
                    h_loso = fit_hgb(Xe.iloc[loso_tr], y[loso_tr], Xe.iloc[half_b], mask)
                    h_ctrl = fit_hgb(Xe.iloc[ctrl_tr], y[ctrl_tr], Xe.iloc[half_b], mask)
                    entry["hgb"] = {"loso": score(y_te, h_loso), "control": score(y_te, h_ctrl)}

                results[key] = entry

            print(f"  done {point}_{regime}_{wd}  "
                  f"({len(qualifying)} services, {time.time() - t0:.0f}s elapsed)")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

cap_key = f"{HEADLINE_CAPACITY:.2f}"
ref = f"at_admission_A_30"

w("## Service composition")
w()
w(f"Reference slice `{ref}`. Sizes and rates differ by regime and window.")
w()
w("| Service | N | Base rate | Qualifies |")
w("|---|---:|---:|---|")
for row in sorted(composition[ref], key=lambda r: -r["n"]):
    w(
        f"| {row['service']} | {row['n']:,} | {row['base_rate']:.2%} | "
        f"{'yes' if row['qualifies'] else 'no'} |"
    )
w()
w(
    f"Services below {MIN_SERVICE_N:,} admissions or {MIN_SERVICE_EVENTS:,} events are "
    "excluded, because a capture statistic on a small test half is too noisy to read."
)
w()

w("## Transfer penalty, logistic")
w()
w(
    "Same held out patients, same training set size, differing only in whether the "
    "service appears in training."
)
w()
w("| Point | Regime | Window | Service | Ctrl AUC | LOSO AUC | Ctrl capture | LOSO capture | Delta |")
w("|---|---|---:|---|---:|---:|---:|---:|---:|")
for r in results.values():
    c, l = r["logit"]["control"], r["logit"]["loso"]
    d = l["capture"][cap_key] - c["capture"][cap_key]
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | {r['service']} | "
        f"{c['auc']:.3f} | {l['auc']:.3f} | {c['capture'][cap_key]:.3f} | "
        f"{l['capture'][cap_key]:.3f} | {d:+.3f} |"
    )
w()

w("## Verdict against the pre registered thresholds")
w()
w("| Point | Regime | Window | Service | Ranking | Level | Predicted | Observed |")
w("|---|---|---:|---|---|---|---:|---:|")
for r in results.values():
    c, l = r["logit"]["control"], r["logit"]["loso"]
    rank_ok = abs(l["capture"][cap_key] - c["capture"][cap_key]) <= CAPTURE_TOLERANCE
    level_gap = abs(l["mean_pred"] - l["observed"])
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | {r['service']} | "
        f"{'transfers' if rank_ok else 'NO'} | "
        f"{'transfers' if level_gap <= LEVEL_TOLERANCE else 'NO'} | "
        f"{l['mean_pred']:.4f} | {l['observed']:.4f} |"
    )
w()

w("## Capture across capacities, logistic")
w()
w("| Point | Regime | Window | Service | Arm | 1% | 5% | 10% | 20% |")
w("|---|---|---:|---|---|---:|---:|---:|---:|")
for r in results.values():
    for arm in ("control", "loso"):
        vals = " | ".join(
            f"{r['logit'][arm]['capture'][f'{c:.2f}']:.3f}" for c in CAPACITIES
        )
        w(f"| {r['point']} | {r['regime']} | {r['window']} | {r['service']} | {arm} | {vals} |")
w()

hgb_rows = [r for r in results.values() if "hgb" in r]
if hgb_rows:
    w("## Gradient boosting spot check")
    w()
    w(
        "Regime A only. `15` ruled gradient boosting out on stability grounds, so this "
        "asks a narrower question: is the transfer penalty a property of the estimator or "
        "of the data. If both estimators lose the same amount, the penalty is the service "
        "shift itself."
    )
    w()
    w("| Point | Window | Service | Logit delta | HGB delta |")
    w("|---|---:|---|---:|---:|")
    for r in hgb_rows:
        ld = r["logit"]["loso"]["capture"][cap_key] - r["logit"]["control"]["capture"][cap_key]
        hd = r["hgb"]["loso"]["capture"][cap_key] - r["hgb"]["control"]["capture"][cap_key]
        w(f"| {r['point']} | {r['window']} | {r['service']} | {ld:+.3f} | {hd:+.3f} |")
    w()

deltas = np.array([
    r["logit"]["loso"]["capture"][cap_key] - r["logit"]["control"]["capture"][cap_key]
    for r in results.values()
])
levels = np.array([
    abs(r["logit"]["loso"]["mean_pred"] - r["logit"]["loso"]["observed"])
    for r in results.values()
])
rank_pass = int((np.abs(deltas) <= CAPTURE_TOLERANCE).sum())
level_pass = int((levels <= LEVEL_TOLERANCE).sum())

w("## Summary")
w()
w("| Quantity | Value |")
w("|---|---:|")
w(f"| Service cells tested | {len(results)} |")
w(f"| Ranking transfers | {rank_pass} of {len(results)} |")
w(f"| Level transfers | {level_pass} of {len(results)} |")
w(f"| Mean capture delta | {deltas.mean():+.4f} |")
w(f"| Worst capture delta | {deltas.min():+.4f} |")
w(f"| Worst level gap | {levels.max():.4f} |")
w()
w(
    "A ranking that transfers and a level that does not is the readable outcome. It means "
    "the model orders patients correctly inside a service it has never seen, but reports "
    "the wrong magnitude of risk, so a programme allocating within one service is fine "
    "and a programme allocating across services would over serve some and under serve "
    "others. That is a recalibration problem rather than a model problem, and it is "
    "stated here rather than discovered at deployment."
)
w()

stats["results"] = results
stats["composition"] = composition
stats["seed"] = SEED
stats["thresholds"] = {
    "capture_tolerance": CAPTURE_TOLERANCE,
    "level_tolerance": LEVEL_TOLERANCE,
    "min_service_n": MIN_SERVICE_N,
    "min_service_events": MIN_SERVICE_EVENTS,
}
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "16_mimic_validation.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "mimic_validation_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.0f}s")
print("Wrote docs/16_mimic_validation.md")
print("Wrote cache/mimic_validation_stats.json")
