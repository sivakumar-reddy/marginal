"""
19_advancement_risk_model.py

What a realistic CRM analytics workflow can learn when its training outcome comes from a
confounded historical visit policy.

THE MODELLING PROBLEM IS NOT THE USUAL ONE
==========================================
In education and in the clinical domain the target was simply the outcome, because no
intervention variable existed in the data. Here one does. `visited` is recorded, the
outcome depends on it, and the assignment was not random.

An advancement shop wanting to prioritise a portfolio needs two quantities:

    baseline risk        probability of giving if nobody visits
    expected effect      how much a visit changes that

Neither is directly observed for any single prospect. What is observed is the outcome
under whichever arm that prospect actually received. This script estimates both from
observable CRM information using the two approaches a real team would reach for.

    S learner   one model fitted on all rows with `visited` as a covariate, then
                predicted twice, at visited 0 and visited 1
    T learner   two models, one fitted on visited rows and one on unvisited rows

Both are biased here, because `18` generated the visit policy from capacity rating and
giving history while the true group membership depends on latent affinity and capacity
that no CRM column measures. That is the point. The bias is the finding, not a defect.

WHAT MAY AND MAY NOT BE USED
============================
Features are CRM observable only. Excluded by name:

    group, y0, y1, tau, p0, p1     ground truth, never available to any shop
    gave                            the outcome
    gift_amount, is_major_gift      derived from the outcome, so leakage

`gift_amount` and `is_major_gift` deserve a note. They look like ordinary CRM fields and
they are, but in this population they are non zero only when `gave` is 1, so including
them would leak the label completely. A real system built carelessly on a CRM extract
could make exactly this mistake.

`visited` IS used, as a covariate. It is a design variable known before the outcome, and
excluding it would make the effect question unanswerable.

BASELINES, PRE REGISTERED
=========================
    B1  prevalence, the training fold base rate predicted for everyone
    B2  one feature logistic on log1p(largest_gift)

Both are reported alongside every model so that a degenerate baseline would be visible.

ESTIMATOR CHOICE IS NOT INHERITED
=================================
Education preferred logistic. The clinical domain measured and also preferred logistic,
but only after `15` showed gradient boosting winning discrimination in all twelve cells
and losing stability in all twelve. Neither result transfers automatically to 50,000 rows
with a 15.6% base rate and a 6% treated share. Both estimators are fitted and compared.

Discrimination alone does not decide. `21` sums predicted probabilities under a capacity
constraint, so calibration is reported with equal weight, and stability is measured
separately in `20`.

GROUND TRUTH IS USED FOR DIAGNOSIS ONLY
=======================================
This domain can do something the other two cannot: check the estimate against the truth.
The final section compares estimated baseline risk against true p0, and estimated effect
against true tau. Those comparisons appear in the report and in the cache. They never
touch a fitted model, and an assertion enforces that the feature matrix excludes every
ground truth column.

Usage:
    python 19_advancement_risk_model.py

Reads:
    data/processed/advancement_population.parquet

Writes:
    data/processed/advancement_risk_oof.parquet
    docs/19_advancement_risk_model.md
    cache/advancement_risk_stats.json
"""

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

SEED = 20260823
N_FOLDS = 5
N_BINS = 10
CAPACITIES = [0.01, 0.03, 0.05, 0.10, 0.20]
HEADLINE_CAPACITY = 0.03          # 1,500 of 50,000, the operational portfolio

GROUND_TRUTH = ["group", "y0", "y1", "tau", "p0", "p1",
                "u_draw", "latent_capacity", "latent_affinity"]
OUTCOME = "gave"
OUTCOME_DERIVED = ["gift_amount", "is_major_gift"]
TREATMENT = "visited"
ID = "prospect_id"

CATEGORICAL = ["region", "grad_decade"]
ESTIMATORS = ["logit", "hgb"]

stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


def ece(y, p, n_bins=N_BINS):
    order = np.argsort(p)
    y, p = np.asarray(y)[order], np.asarray(p)[order]
    err, total = 0.0, 0
    for b in np.array_split(np.arange(len(y)), n_bins):
        if len(b) == 0:
            continue
        err += len(b) * abs(p[b].mean() - y[b].mean())
        total += len(b)
    return err / total if total else np.nan


def capture(y, p, cap):
    k = max(1, int(round(cap * len(p))))
    sel = np.argsort(-p, kind="stable")[:k]
    return float(y[sel].sum() / y.sum()) if y.sum() else np.nan


def make_logit(cats, nums):
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=25), cats),
        ("num", StandardScaler(), nums),
    ])
    return make_pipeline(pre, LogisticRegression(max_iter=2000, solver="lbfgs"))


def make_hgb(mask):
    return HistGradientBoostingClassifier(
        categorical_features=mask, random_state=SEED,
        early_stopping=True, validation_fraction=0.15,
    )


t0 = time.time()
df = pd.read_parquet(PROC / "advancement_population.parquet")
n = len(df)

FEATURES = [
    c for c in df.columns
    if c not in GROUND_TRUTH + OUTCOME_DERIVED + [OUTCOME, ID]
]
assert TREATMENT in FEATURES, "treatment must be a covariate"
for c in GROUND_TRUTH + OUTCOME_DERIVED + [OUTCOME]:
    assert c not in FEATURES, f"leakage: {c} present in features"

cats = [c for c in CATEGORICAL if c in FEATURES]
nums = [c for c in FEATURES if c not in cats]

X = df[FEATURES].copy()
for c in cats:
    X[c] = X[c].astype(str)
Xe = X.copy()
if cats:
    Xe[cats] = OrdinalEncoder().fit_transform(X[cats])
Xe = Xe.astype(float)
mask = [c in cats for c in Xe.columns]

y = df[OUTCOME].to_numpy()
v = df[TREATMENT].to_numpy()

rng = np.random.default_rng(SEED)
perm = rng.permutation(n)
folds = np.empty(n, dtype=int)
for i, part in enumerate(np.array_split(perm, N_FOLDS)):
    folds[part] = i

oof = {
    f"{m}_{q}": np.full(n, np.nan)
    for m in ESTIMATORS for q in ["p_obs", "p0_s", "p1_s", "p0_t", "p1_t"]
}
oof["b1"] = np.full(n, np.nan)
oof["b2"] = np.full(n, np.nan)

for f in range(N_FOLDS):
    tr, te = folds != f, folds == f

    oof["b1"][te] = y[tr].mean()
    b2 = make_logit([], ["largest_gift_log"])
    tmp_tr = pd.DataFrame({"largest_gift_log": np.log1p(df.loc[tr, "largest_gift"])})
    tmp_te = pd.DataFrame({"largest_gift_log": np.log1p(df.loc[te, "largest_gift"])})
    b2.fit(tmp_tr, y[tr])
    oof["b2"][te] = b2.predict_proba(tmp_te)[:, 1]

    for m in ESTIMATORS:
        if m == "logit":
            Xtr, Xte = X[tr], X[te]
            fit = lambda a, b: make_logit(cats, nums).fit(a, b)
            X0 = X[te].copy(); X0[TREATMENT] = 0
            X1 = X[te].copy(); X1[TREATMENT] = 1
        else:
            Xtr, Xte = Xe[tr], Xe[te]
            fit = lambda a, b: make_hgb(mask).fit(a, b)
            X0 = Xe[te].copy(); X0[TREATMENT] = 0.0
            X1 = Xe[te].copy(); X1[TREATMENT] = 1.0

        s = fit(Xtr, y[tr])
        oof[f"{m}_p_obs"][te] = s.predict_proba(Xte)[:, 1]
        oof[f"{m}_p0_s"][te] = s.predict_proba(X0)[:, 1]
        oof[f"{m}_p1_s"][te] = s.predict_proba(X1)[:, 1]

        tr0 = tr & (v == 0)
        tr1 = tr & (v == 1)
        t_0 = fit(Xtr[v[tr] == 0] if False else (X[tr0] if m == "logit" else Xe[tr0]), y[tr0])
        t_1 = fit(X[tr1] if m == "logit" else Xe[tr1], y[tr1])
        oof[f"{m}_p0_t"][te] = t_0.predict_proba(Xte)[:, 1]
        oof[f"{m}_p1_t"][te] = t_1.predict_proba(Xte)[:, 1]

    print(f"  fold {f} done ({time.time() - t0:.0f}s)")

out = pd.DataFrame({ID: df[ID].to_numpy(), "fold": folds, OUTCOME: y, TREATMENT: v})
for k, arr in oof.items():
    out[k] = arr
for m in ESTIMATORS:
    out[f"{m}_tau_s"] = out[f"{m}_p1_s"] - out[f"{m}_p0_s"]
    out[f"{m}_tau_t"] = out[f"{m}_p1_t"] - out[f"{m}_p0_t"]
assert out.notna().all().all(), "every row must receive an out of fold prediction"
out.to_parquet(PROC / "advancement_risk_oof.parquet", index=False)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

w("# 19. Advancement risk model")
w()
w("Generated by `19_advancement_risk_model.py`. Do not edit by hand.")
w()
w(
    "Simulation. The population is constructed by `18` and nothing here is evidence about "
    "real donors."
)
w()
w(
    f"{n:,} prospects, {N_FOLDS} deterministic folds from seed {SEED}. Outcome is "
    f"`{OUTCOME}` at {y.mean():.2%}. Treatment is `{TREATMENT}` at {v.mean():.2%}, "
    "assigned by a confounded historical policy."
)
w()

w("## Feature boundary")
w()
w("| Status | Columns |")
w("|---|---|")
w(f"| Used | {', '.join(FEATURES)} |")
w(f"| Excluded, ground truth | {', '.join(GROUND_TRUTH)} |")
w(f"| Excluded, outcome derived | {', '.join(OUTCOME_DERIVED)} |")
w()
w(
    "`gift_amount` and `is_major_gift` look like ordinary CRM fields but are non zero only "
    "when the outcome is 1, so they leak the label. A system built carelessly on a CRM "
    "extract could include them."
)
w()

w("## Discrimination and calibration on the observed outcome")
w()
w(
    "Predictions are scored at the arm each prospect actually received, which is the only "
    "thing a shop could ever validate against."
)
w()
w("| Model | AUC | Brier | ECE |")
w("|---|---:|---:|---:|")
perf = {}
for name, p in [("B1 prevalence", oof["b1"]), ("B2 one feature", oof["b2"])] + \
               [(f"{m} S learner", oof[f"{m}_p_obs"]) for m in ESTIMATORS]:
    auc = float(roc_auc_score(y, p)) if len(np.unique(p)) > 1 else float("nan")
    perf[name] = {
        "auc": auc, "brier": float(brier_score_loss(y, p)), "ece": float(ece(y, p)),
    }
    w(f"| {name} | {auc:.4f} | {perf[name]['brier']:.4f} | {perf[name]['ece']:.4f} |")
w()

w("## Calibration by decile, best model")
w()
best = max(ESTIMATORS, key=lambda m: perf[f"{m} S learner"]["auc"])
p_best = oof[f"{best}_p_obs"]
w(f"Model: `{best}`.")
w()
w("| Bin | N | Predicted | Observed | Gap |")
w("|---:|---:|---:|---:|---:|")
order = np.argsort(p_best)
cal = []
for i, b in enumerate(np.array_split(order, N_BINS)):
    row = {
        "bin": i + 1, "n": int(len(b)),
        "predicted": float(p_best[b].mean()), "observed": float(y[b].mean()),
    }
    row["gap"] = row["observed"] - row["predicted"]
    cal.append(row)
    w(f"| {i+1} | {row['n']:,} | {row['predicted']:.4f} | {row['observed']:.4f} | "
      f"{row['gap']:+.4f} |")
w()

w("## Capture at capacity, observed outcome")
w()
w(f"Operational capacity is {HEADLINE_CAPACITY:.0%}, "
  f"{int(round(HEADLINE_CAPACITY * n)):,} of {n:,}.")
w()
w("| Model | " + " | ".join(f"{c:.0%}" for c in CAPACITIES) + " |")
w("|---|" + "---:|" * len(CAPACITIES))
cap_tbl = {}
for name, p in [("B2 one feature", oof["b2"])] + \
               [(f"{m} S learner", oof[f"{m}_p_obs"]) for m in ESTIMATORS]:
    vals = [capture(y, p, c) for c in CAPACITIES]
    cap_tbl[name] = {f"{c:.2f}": float(x) for c, x in zip(CAPACITIES, vals)}
    w(f"| {name} | " + " | ".join(f"{x:.3f}" for x in vals) + " |")
w()

w("## Ground truth diagnostics")
w()
w(
    "Available in this domain and in no other, because `18` generated both potential "
    "outcomes. None of this entered any model. It measures how far a competent "
    "observational workflow lands from the truth it is trying to recover."
)
w()
w("| Model | Learner | corr with true p0 | corr with true tau | Mean est. tau | True mean tau |")
w("|---|---|---:|---:|---:|---:|")
diag = {}
true_p0, true_tau = df["p0"].to_numpy(), df["tau"].to_numpy()
for m in ESTIMATORS:
    for lr in ["s", "t"]:
        p0h = out[f"{m}_p0_{lr}"].to_numpy()
        tauh = out[f"{m}_tau_{lr}"].to_numpy()
        d = {
            "corr_p0": float(np.corrcoef(p0h, true_p0)[0, 1]),
            "corr_tau": float(np.corrcoef(tauh, true_tau)[0, 1]),
            "mean_tau_hat": float(tauh.mean()),
        }
        diag[f"{m}_{lr}"] = d
        w(f"| {m} | {lr.upper()} learner | {d['corr_p0']:.4f} | {d['corr_tau']:.4f} | "
          f"{d['mean_tau_hat']:+.4f} | {true_tau.mean():+.4f} |")
w()
w(
    "A correlation with true tau near zero would mean the effect ranking carries no "
    "information about who actually benefits, in which case `21` is comparing risk "
    "ranking against noise and must say so."
)
w()

w("## Does the model recover the negative effect group?")
w()
w(
    "The do not disturb group is the mechanism that makes this domain different. If no "
    "estimator assigns it a negative estimated effect, the effect ranking cannot avoid "
    "harming it and that is a finding in itself."
)
w()
w("| Group | True mean tau | " + " | ".join(f"{m} {lr.upper()}" for m in ESTIMATORS for lr in ["s", "t"]) + " |")
w("|---|---:|" + "---:|" * (len(ESTIMATORS) * 2))
grp = {}
for g in ["sure_thing", "persuadable", "lost_cause", "do_not_disturb"]:
    msk = (df["group"] == g).to_numpy()
    row = {"true": float(true_tau[msk].mean())}
    cells = []
    for m in ESTIMATORS:
        for lr in ["s", "t"]:
            val = float(out.loc[msk, f"{m}_tau_{lr}"].mean())
            row[f"{m}_{lr}"] = val
            cells.append(f"{val:+.4f}")
    grp[g] = row
    w(f"| {g} | {row['true']:+.4f} | " + " | ".join(cells) + " |")
w()

w("## Limitations")
w()
w(
    "The historical policy is confounded by construction, so every effect estimate here is "
    "biased and no amount of model choice removes that. The parameters in `18` are "
    "illustrative and open in `08_sources.md`. Nothing in this document is a claim about "
    "real donor behaviour."
)
w()

stats["seed"] = SEED
stats["n"] = int(n)
stats["n_folds"] = N_FOLDS
stats["features"] = FEATURES
stats["excluded_ground_truth"] = GROUND_TRUTH
stats["excluded_outcome_derived"] = OUTCOME_DERIVED
stats["base_rate"] = float(y.mean())
stats["treated_rate"] = float(v.mean())
stats["performance"] = perf
stats["calibration_best"] = {"model": best, "bins": cal}
stats["capture"] = cap_tbl
stats["capacities"] = CAPACITIES
stats["headline_capacity"] = HEADLINE_CAPACITY
stats["ground_truth_diagnostics"] = diag
stats["group_effect_recovery"] = grp
stats["true_mean_tau"] = float(true_tau.mean())
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "19_advancement_risk_model.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "advancement_risk_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.1f}s")
print("Wrote data/processed/advancement_risk_oof.parquet")
print("Wrote docs/19_advancement_risk_model.md")
print("Wrote cache/advancement_risk_stats.json")
