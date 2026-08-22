"""
14_mimic_risk_model.py

Fits the risk model for the academic medical center domain across the full grid.

    2 decision points  x  3 censoring regimes  x  2 windows  x  2 estimators  x  5 folds
    = 120 model fits on populations of 320,000 to 530,000 rows.

Nothing is collapsed. The argument for three regimes is that the censoring choice is
carried forward rather than hidden, and dropping half the grid at the modelling step to
save runtime would undercut it. The same applies to the window.

BOTH ESTIMATORS, NOT ONE
========================
`07_stability.md` found logistic regression the most stable of three estimators on OULAD,
and `06_allocation.py` was rebuilt around it. That finding is about a population of 2,285
students. It may or may not transfer to 320,000 admissions with different feature
structure, and assuming it does would be exactly the kind of unexamined inheritance this
project exists to interrogate. Both estimators are fitted and compared here, and the
allocation step uses whichever is more stable on THIS data, established in the MIMIC
stability script rather than borrowed.

PRE REGISTERED BASELINES
========================
    B1. Prevalence. Training fold base rate for everyone.
    B2. Single feature logistic on log1p(prior_admissions). A patient who has been
        admitted often will be admitted again; if a model cannot beat that, its
        complexity is not earning anything.

`04_risk_model.py` had a baseline silently degenerate because a sentinel value destroyed
the feature scale. B2 here uses a count with no sentinel, and the report shows B1 and B2
side by side so a collapse would be visible rather than silent.

CALIBRATION BEFORE DISCRIMINATION
=================================
The allocation step sums predicted probabilities to estimate outcomes averted. Ranking
alone is not enough. Brier score and expected calibration error lead; AUC is secondary.

NOT DONE, STATED SO IT IS NOT MISTAKEN FOR DONE
===============================================
No hyperparameter search. Defaults, deliberately, because tuning against these folds
would contaminate the folds the allocation comparison depends on.

No leave one service out. That is `15_mimic_validation.py`. MED is 51.73% of admissions,
so within fold performance will overstate what a model achieves on an unseen service.

Usage:
    python 14_mimic_risk_model.py

Reads:
    data/processed/mimic_features_at_admission.parquet
    data/processed/mimic_features_at_discharge.parquet

Writes:
    data/processed/mimic_risk_oof.parquet
    docs/14_mimic_risk_model.md
    cache/mimic_risk_stats.json
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
N_BINS = 10
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


def calibration_table(y, p, n_bins=N_BINS):
    order = np.argsort(p)
    y, p = np.asarray(y)[order], np.asarray(p)[order]
    rows = []
    for i, b in enumerate(np.array_split(np.arange(len(y)), n_bins)):
        if len(b) == 0:
            continue
        rows.append({"bin": i + 1, "n": len(b), "pred": float(p[b].mean()), "obs": float(y[b].mean())})
    return rows


def fit_hgb(Xtr, ytr, Xte, mask):
    clf = HistGradientBoostingClassifier(
        categorical_features=mask, random_state=SEED,
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


w("# 14. MIMIC risk model")
w()
w("Generated by `14_mimic_risk_model.py`. Do not edit by hand.")
w()
w(
    "Full grid: two decision points, three censoring regimes, two windows, two "
    "estimators, five folds. 120 fits. Nothing collapsed."
)
w()
w("## Pre registered baselines")
w()
w("| Baseline | Definition |")
w("|---|---|")
w("| B1 Prevalence | Training fold base rate predicted for everyone |")
w("| B2 One feature | Logistic on log1p(prior_admissions) |")
w()
w(
    "Both are reported alongside every model so that a degenerate baseline, which "
    "happened once in `04_risk_model.py`, would be visible rather than silent."
)
w()
w(
    "Both estimators are fitted rather than inheriting the education domain's choice. "
    "That finding came from a population of 2,285 students and may not transfer to "
    "320,000 admissions."
)
w()

results = {}
oof_frames = []
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

            oof = {"hgb": np.zeros(len(s)), "logit": np.zeros(len(s))}
            oof_b1 = np.zeros(len(s))
            oof_b2 = np.zeros(len(s))
            per_fold = {"hgb": [], "logit": []}

            for f in sorted(np.unique(folds)):
                tr, te = folds != f, folds == f

                oof_b1[te] = y[tr].mean()

                s_tr = np.log1p(s.loc[tr, "prior_admissions"].to_numpy()).reshape(-1, 1)
                s_te = np.log1p(s.loc[te, "prior_admissions"].to_numpy()).reshape(-1, 1)
                mu, sd = s_tr.mean(), s_tr.std() or 1.0
                lr = LogisticRegression(max_iter=1000)
                lr.fit((s_tr - mu) / sd, y[tr])
                oof_b2[te] = lr.predict_proba((s_te - mu) / sd)[:, 1]

                p_h = fit_hgb(Xe[tr], y[tr], Xe[te], mask)
                p_l = fit_logit(X[tr], y[tr], X[te], cats, nums)
                oof["hgb"][te] = p_h
                oof["logit"][te] = p_l

                for m, p in (("hgb", p_h), ("logit", p_l)):
                    per_fold[m].append({
                        "fold": int(f),
                        "brier": float(brier_score_loss(y[te], p)),
                        "auc": float(roc_auc_score(y[te], p)),
                    })

            key = f"{point}_{regime}_{wd}"
            results[key] = {
                "point": point, "regime": regime, "window": wd,
                "n": int(len(s)), "base_rate_pct": float(y.mean() * 100),
                "b1_brier": float(brier_score_loss(y, oof_b1)),
                "b2_brier": float(brier_score_loss(y, oof_b2)),
                "b2_auc": float(roc_auc_score(y, oof_b2)),
            }
            for m in ("hgb", "logit"):
                briers = np.array([r["brier"] for r in per_fold[m]])
                aucs = np.array([r["auc"] for r in per_fold[m]])
                results[key][m] = {
                    "brier": float(brier_score_loss(y, oof[m])),
                    "auc": float(roc_auc_score(y, oof[m])),
                    "ece": float(ece(y, oof[m])),
                    "brier_fold_sd": float(briers.std(ddof=1)),
                    "auc_fold_sd": float(aucs.std(ddof=1)),
                    "calibration": calibration_table(y, oof[m]),
                }

            out = s[["subject_id", "hadm_id", "fold", "readmit"]].copy()
            out["point"], out["regime"], out["window"] = point, regime, wd
            out["risk_hgb"] = oof["hgb"]
            out["risk_logit"] = oof["logit"]
            oof_frames.append(out)

            print(f"  done {key}  ({time.time() - t0:.0f}s elapsed)")

pd.concat(oof_frames, ignore_index=True).to_parquet(PROC / "mimic_risk_oof.parquet", index=False)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

w("## Results")
w()
w("| Point | Regime | Window | N | Base rate | B1 | B2 | HGB Brier | HGB AUC | Logit Brier | Logit AUC |")
w("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for k, r in results.items():
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | {r['n']:,} | "
        f"{r['base_rate_pct']:.2f}% | {r['b1_brier']:.4f} | {r['b2_brier']:.4f} | "
        f"{r['hgb']['brier']:.4f} | {r['hgb']['auc']:.3f} | "
        f"{r['logit']['brier']:.4f} | {r['logit']['auc']:.3f} |"
    )
w()

w("### Does the model beat its baselines?")
w()
w("| Point | Regime | Window | HGB beats B1 | HGB beats B2 | Logit beats B2 |")
w("|---|---|---:|---|---|---|")
for k, r in results.items():
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | "
        f"{'yes' if r['hgb']['brier'] < r['b1_brier'] else 'NO'} | "
        f"{'yes' if r['hgb']['brier'] < r['b2_brier'] else 'NO'} | "
        f"{'yes' if r['logit']['brier'] < r['b2_brier'] else 'NO'} |"
    )
w()

w("### Does information at discharge beat information at admission?")
w()
w(
    "The same admissions and the same outcome, differing only in what is known. This is "
    "the clinical form of the reach against information trade the education domain found."
)
w()
w("| Regime | Window | AUC at admission | AUC at discharge | Difference |")
w("|---|---:|---:|---:|---:|")
for regime in REGIMES:
    for wd in WINDOWS:
        a = results[f"at_admission_{regime}_{wd}"]["hgb"]["auc"]
        d = results[f"at_discharge_{regime}_{wd}"]["hgb"]["auc"]
        sd = results[f"at_admission_{regime}_{wd}"]["hgb"]["auc_fold_sd"]
        w(f"| {regime} | {wd} | {a:.3f} | {d:.3f} | {d - a:+.3f} (fold SD {sd:.3f}) |")
w()
w(
    "A difference smaller than the fold standard deviation is not a difference. If "
    "discharge information does not improve the ranking, then the decision point that "
    "still allows the stay to be changed costs nothing in accuracy, which is the same "
    "shape of result the education domain produced for day 0."
)
w()

w("### Does the censoring regime change the ranking quality?")
w()
w("| Point | Window | AUC under A | under B | under C | Spread |")
w("|---|---:|---:|---:|---:|---:|")
for point in POINTS:
    for wd in WINDOWS:
        vals = [results[f"{point}_{r}_{wd}"]["hgb"]["auc"] for r in REGIMES]
        w(
            f"| {point} | {wd} | {vals[0]:.3f} | {vals[1]:.3f} | {vals[2]:.3f} | "
            f"{max(vals) - min(vals):.3f} |"
        )
w()
w(
    "The regimes differ in base rate by more than thirteen points. If AUC is stable "
    "across them, discrimination is insensitive to the censoring choice even though the "
    "reported rate is not. Calibration is a different question and is examined below."
)
w()

w("### Calibration, 30 day window")
w()
for point in POINTS:
    for regime in REGIMES:
        r = results[f"{point}_{regime}_30"]
        w(f"**{point}, regime {regime}** (ECE {r['hgb']['ece']:.4f})")
        w()
        w("| Bin | N | Predicted | Observed | Gap |")
        w("|---:|---:|---:|---:|---:|")
        for b in r["hgb"]["calibration"]:
            w(f"| {b['bin']} | {b['n']:,} | {b['pred']:.4f} | {b['obs']:.4f} | {b['obs'] - b['pred']:+.4f} |")
        w()

w("## Which estimator carries forward")
w()
w(
    "Discrimination and calibration are reported above for both. Stability, which is what "
    "the allocation step actually needs, is measured in `15_mimic_stability.py` on this "
    "data rather than inherited from the education domain."
)
w()

stats["results"] = results
stats["seed"] = SEED
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "14_mimic_risk_model.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "mimic_risk_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.0f}s")
print("Wrote data/processed/mimic_risk_oof.parquet")
print("Wrote docs/14_mimic_risk_model.md")
print("Wrote cache/mimic_risk_stats.json")
