"""
19b_advancement_effect_recovery.py

`19` found that no estimator recovered the do not disturb group. All four assigned it a
positive effect against a true value of -0.185, and correlation with true tau ran 0.085 to
0.194.

That result cannot be reported until it is attributed, because three different things
could produce it and they have opposite consequences.

    A. SPECIFICATION
       A logistic S learner with `visited` as a single main effect and no treatment by
       feature interactions is structurally incapable of heterogeneous effects. Its tau is
       near constant by construction. If that is the whole story, `19` measured my model
       form and the fix is a better estimator.

    B. CONFOUNDING
       `18` assigns visits on capacity rating and giving history, which also drive giving
       without a visit. If that is the cause, the fix is a design change no shop can make
       retrospectively, and the finding is about observational data rather than about
       method.

    C. INFORMATION LIMIT
       `18` builds group membership from latent affinity and capacity. The CRM columns are
       noisy proxies for those latents. If tau is simply not a function of the observables,
       then no estimator and no experiment recovers it, and the ceiling is the feature set.

The three are separated by running the same estimators under conditions that vary one
cause at a time.

THE THREE ARMS
==============
    observed        the real pipeline. Confounded policy, CRM features.
                    Varying the estimator here tests A.

    randomised      a diagnostic dataset only. Visits reassigned at random with a fixed
                    seed, outcome taken from the matching potential outcome. Nothing is
                    written back and `18` is untouched. Comparing this against `observed`
                    at the same estimator isolates B.

    ceiling         true tau regressed directly on the observable features. This is not an
                    estimator anyone could deploy, because it consumes ground truth. It
                    answers only how much of tau the observables can express at all,
                    which is C.

The randomised arm does not remove the confounding from the project. `18` and `19` keep it
exactly as designed. This arm exists so the confounding can be quantified rather than
merely asserted.

ESTIMATORS
==========
    s_main      logistic, treatment as a main effect only. The `19` specification.
    s_inter     logistic, treatment interacted with every feature.
    t_learner   two logistic models, one per arm.
    x_learner   Künzel style, imputed effects with propensity weighting.
    hgb_s       gradient boosting, treatment as a feature, interactions available.

PRE REGISTERED READING
======================
Fixed before running.

    If s_inter and x_learner recover a negative mean effect for do not disturb under the
    observed arm, cause A dominates and `19`'s effect columns must be regenerated with a
    better estimator before `21` uses them.

    If they do not, but the same estimators recover it under the randomised arm, cause B
    dominates. The finding is that observational CRM history cannot support effect
    ranking, which is a substantive result about advancement analytics.

    If they recover it under neither, but the ceiling arm shows true tau is predictable
    from observables, something is wrong with the estimators and the script has a bug.

    If the ceiling arm itself is weak, cause C dominates and the honest statement is that
    in this population effect ranking is not estimable from the CRM, whatever method is
    used and whatever the assignment mechanism.

Correlation with true tau is reported for every combination, alongside the quantity that
actually matters for allocation: the share of a selected portfolio whose true effect is
negative.

Usage:
    python 19b_advancement_effect_recovery.py

Reads:
    data/processed/advancement_population.parquet

Writes:
    docs/19b_advancement_effect_recovery.md
    cache/advancement_effect_recovery_stats.json
"""

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

SEED = 20260823
N_FOLDS = 5
HEADLINE_CAPACITY = 0.03

GROUND_TRUTH = ["group", "y0", "y1", "tau", "p0", "p1"]
OUTCOME_DERIVED = ["gift_amount", "is_major_gift"]
OUTCOME, TREATMENT, ID = "gave", "visited", "prospect_id"
CATEGORICAL = ["region", "grad_decade"]

GROUPS = ["sure_thing", "persuadable", "lost_cause", "do_not_disturb"]
ESTIMATORS = ["s_main", "s_inter", "t_learner", "x_learner", "hgb_s"]
ARMS = ["observed", "randomised"]

stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


def lr():
    return LogisticRegression(max_iter=3000, solver="lbfgs")


def hgb():
    return HistGradientBoostingClassifier(
        random_state=SEED, early_stopping=True, validation_fraction=0.15
    )


def tau_oof(name, D, Dv, y, v, folds):
    """Out of fold estimated individual effect for one estimator."""
    n = len(y)
    out = np.full(n, np.nan)

    for f in range(N_FOLDS):
        tr, te = folds != f, folds == f

        if name in ("s_main", "s_inter", "hgb_s"):
            A = Dv[name]
            A0, A1 = A["at0"], A["at1"]
            model = hgb() if name == "hgb_s" else lr()
            model.fit(A["full"][tr], y[tr])
            out[te] = (
                model.predict_proba(A1[te])[:, 1] - model.predict_proba(A0[te])[:, 1]
            )

        elif name == "t_learner":
            m0, m1 = lr(), lr()
            m0.fit(D[tr & (v == 0)], y[tr & (v == 0)])
            m1.fit(D[tr & (v == 1)], y[tr & (v == 1)])
            out[te] = m1.predict_proba(D[te])[:, 1] - m0.predict_proba(D[te])[:, 1]

        elif name == "x_learner":
            i0, i1 = tr & (v == 0), tr & (v == 1)
            m0, m1 = lr(), lr()
            m0.fit(D[i0], y[i0])
            m1.fit(D[i1], y[i1])
            d1 = y[i1] - m0.predict_proba(D[i1])[:, 1]
            d0 = m1.predict_proba(D[i0])[:, 1] - y[i0]
            t1, t0 = Ridge(alpha=1.0), Ridge(alpha=1.0)
            t1.fit(D[i1], d1)
            t0.fit(D[i0], d0)
            ps = lr()
            ps.fit(D[tr], v[tr])
            e = np.clip(ps.predict_proba(D[te])[:, 1], 0.01, 0.99)
            out[te] = e * t0.predict(D[te]) + (1 - e) * t1.predict(D[te])

    assert not np.isnan(out).any(), f"{name} left rows unscored"
    return out


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

true_tau = df["tau"].to_numpy()
true_group = df["group"].to_numpy()
y0, y1 = df["y0"].to_numpy(), df["y1"].to_numpy()

rng = np.random.default_rng(SEED)
perm = rng.permutation(n)
folds = np.empty(n, dtype=int)
for i, part in enumerate(np.array_split(perm, N_FOLDS)):
    folds[part] = i

v_obs = df[TREATMENT].to_numpy()
rate = v_obs.mean()
rng_r = np.random.default_rng(SEED + 991)
v_rand = (rng_r.random(n) < rate).astype(int)

arms_data = {
    "observed": (v_obs, np.where(v_obs == 1, y1, y0)),
    "randomised": (v_rand, np.where(v_rand == 1, y1, y0)),
}

k_head = max(1, int(round(HEADLINE_CAPACITY * n)))
results = {}

for arm, (v, y) in arms_data.items():
    Dv = {}
    for name in ["s_main", "s_inter", "hgb_s"]:
        if name == "s_inter":
            inter = D * v[:, None]
            full = np.hstack([D, v[:, None], inter])
            at0 = np.hstack([D, np.zeros((n, 1)), np.zeros_like(D)])
            at1 = np.hstack([D, np.ones((n, 1)), D])
        else:
            full = np.hstack([D, v[:, None]])
            at0 = np.hstack([D, np.zeros((n, 1))])
            at1 = np.hstack([D, np.ones((n, 1))])
        Dv[name] = {"full": full, "at0": at0, "at1": at1}

    for name in ESTIMATORS:
        th = tau_oof(name, D, Dv, y, v, folds)
        sel = np.argsort(-th, kind="stable")[:k_head]
        entry = {
            "corr_tau": float(np.corrcoef(th, true_tau)[0, 1]),
            "mean_tau_hat": float(th.mean()),
            "by_group": {
                g: float(th[true_group == g].mean()) for g in GROUPS
            },
            "dnd_negative": bool(th[true_group == "do_not_disturb"].mean() < 0),
            "selected_true_tau": float(true_tau[sel].mean()),
            "selected_harm_share": float((true_tau[sel] < 0).mean()),
            "selected_dnd_share": float((true_group[sel] == "do_not_disturb").mean()),
        }
        results[f"{arm}|{name}"] = entry
        print(f"  {arm:11s} {name:10s} corr={entry['corr_tau']:+.4f} "
              f"dnd={entry['by_group']['do_not_disturb']:+.4f} "
              f"({time.time() - t0:.0f}s)")

# ceiling: true tau regressed on observables. Not deployable, diagnostic only.
ceil = np.full(n, np.nan)
for f in range(N_FOLDS):
    tr, te = folds != f, folds == f
    r = Ridge(alpha=1.0).fit(D[tr], true_tau[tr])
    ceil[te] = r.predict(D[te])
ceiling = {
    "corr_tau": float(np.corrcoef(ceil, true_tau)[0, 1]),
    "r2": float(1 - ((true_tau - ceil) ** 2).sum() / ((true_tau - true_tau.mean()) ** 2).sum()),
}
sel_c = np.argsort(-ceil, kind="stable")[:k_head]
ceiling["selected_true_tau"] = float(true_tau[sel_c].mean())
ceiling["selected_harm_share"] = float((true_tau[sel_c] < 0).mean())

oracle_sel = np.argsort(-true_tau, kind="stable")[:k_head]
oracle = {
    "selected_true_tau": float(true_tau[oracle_sel].mean()),
    "selected_harm_share": float((true_tau[oracle_sel] < 0).mean()),
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

w("# 19b. Why did no estimator find the negative effect group?")
w()
w("Generated by `19b_advancement_effect_recovery.py`. Do not edit by hand.")
w()
w(
    "Simulation. `19` reported that every estimator assigned the do not disturb group a "
    "positive effect against a true value of "
    f"{true_tau[true_group == 'do_not_disturb'].mean():+.4f}. This script attributes that "
    "result to one of three causes before it is allowed to become a finding."
)
w()
w("| Cause | Isolated by |")
w("|---|---|")
w("| A specification | varying the estimator within the observed arm |")
w("| B confounding | the same estimator across observed and randomised arms |")
w("| C information limit | the ceiling arm, true tau regressed on observables |")
w()
w(
    "The randomised arm is a diagnostic dataset built inside this script. Visits are "
    "reassigned at random with a fixed seed and the outcome is taken from the matching "
    "potential outcome. `18` is untouched and the project pipeline keeps its confounded "
    "policy exactly as designed."
)
w()

w("## Correlation with true individual effect")
w()
w("| Estimator | Observed | Randomised | Change |")
w("|---|---:|---:|---:|")
for e in ESTIMATORS:
    a = results[f"observed|{e}"]["corr_tau"]
    b = results[f"randomised|{e}"]["corr_tau"]
    w(f"| {e} | {a:+.4f} | {b:+.4f} | {b - a:+.4f} |")
w()
w(f"| ceiling, true tau on observables | {ceiling['corr_tau']:+.4f} | | |")
w()

w("## Estimated effect for the do not disturb group")
w()
w(
    f"True value {true_tau[true_group == 'do_not_disturb'].mean():+.4f}. A positive "
    "estimate here means the method would rank a harmful prospect as a beneficiary."
)
w()
w("| Estimator | Observed | Randomised |")
w("|---|---:|---:|")
for e in ESTIMATORS:
    a = results[f"observed|{e}"]["by_group"]["do_not_disturb"]
    b = results[f"randomised|{e}"]["by_group"]["do_not_disturb"]
    w(f"| {e} | {a:+.4f} | {b:+.4f} |")
w()

w("## Estimated effect by group, observed arm")
w()
w("| Group | True | " + " | ".join(ESTIMATORS) + " |")
w("|---|---:|" + "---:|" * len(ESTIMATORS))
for g in GROUPS:
    tv = float(true_tau[true_group == g].mean())
    cells = " | ".join(
        f"{results[f'observed|{e}']['by_group'][g]:+.4f}" for e in ESTIMATORS
    )
    w(f"| {g} | {tv:+.4f} | {cells} |")
w()

w(f"## What a portfolio of {k_head:,} selected on estimated effect actually contains")
w()
w(
    "The allocation consequence. Harm share is the fraction of the selected portfolio "
    "whose true effect is negative, meaning the visit makes them less likely to give."
)
w()
w("| Arm | Estimator | Mean true effect | Harm share | DND share |")
w("|---|---|---:|---:|---:|")
for arm in ARMS:
    for e in ESTIMATORS:
        r = results[f"{arm}|{e}"]
        w(
            f"| {arm} | {e} | {r['selected_true_tau']:+.4f} | "
            f"{r['selected_harm_share']:.1%} | {r['selected_dnd_share']:.1%} |"
        )
w(f"| ceiling | true tau on observables | {ceiling['selected_true_tau']:+.4f} | "
  f"{ceiling['selected_harm_share']:.1%} | |")
w(f"| oracle | true tau directly | {oracle['selected_true_tau']:+.4f} | "
  f"{oracle['selected_harm_share']:.1%} | |")
w()

best_obs = max(ESTIMATORS, key=lambda e: results[f"observed|{e}"]["corr_tau"])
best_rand = max(ESTIMATORS, key=lambda e: results[f"randomised|{e}"]["corr_tau"])
any_neg_obs = any(results[f"observed|{e}"]["dnd_negative"] for e in ESTIMATORS)
any_neg_rand = any(results[f"randomised|{e}"]["dnd_negative"] for e in ESTIMATORS)

w("## Attribution")
w()
w("| Question | Answer |")
w("|---|---|")
w(f"| Best estimator, observed | {best_obs} at {results[f'observed|{best_obs}']['corr_tau']:+.4f} |")
w(f"| Best estimator, randomised | {best_rand} at {results[f'randomised|{best_rand}']['corr_tau']:+.4f} |")
w(f"| Any estimator recovers negative DND, observed | {'yes' if any_neg_obs else 'no'} |")
w(f"| Any estimator recovers negative DND, randomised | {'yes' if any_neg_rand else 'no'} |")
w(f"| Ceiling correlation | {ceiling['corr_tau']:+.4f} |")
w(f"| Ceiling R squared | {ceiling['r2']:+.4f} |")
w()
w(
    "Read against the pre registered rules in the docstring. The ceiling arm bounds every "
    "other row: no deployable method can exceed what the observables can express, and the "
    "gap between the ceiling and the oracle is the part of the effect that lives in "
    "latent traits no CRM records."
)
w()

w("## Limitations")
w()
w(
    "The randomised arm is counterfactual and could not be run by any institution without "
    "an actual experiment. The ceiling arm consumes ground truth and is not deployable. "
    "Both exist to attribute a failure, not to propose a method. All parameters remain "
    "illustrative and open in `08_sources.md`."
)
w()

stats["seed"] = SEED
stats["n"] = int(n)
stats["headline_capacity"] = HEADLINE_CAPACITY
stats["k_headline"] = int(k_head)
stats["estimators"] = ESTIMATORS
stats["arms"] = ARMS
stats["results"] = results
stats["ceiling"] = ceiling
stats["oracle"] = oracle
stats["true_dnd_tau"] = float(true_tau[true_group == "do_not_disturb"].mean())
stats["attribution"] = {
    "best_observed": best_obs,
    "best_randomised": best_rand,
    "any_negative_dnd_observed": any_neg_obs,
    "any_negative_dnd_randomised": any_neg_rand,
}
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "19b_advancement_effect_recovery.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "advancement_effect_recovery_stats.json").write_text(
    json.dumps(stats, indent=2), encoding="utf-8"
)

print()
print(f"Total runtime: {time.time() - t0:.1f}s")
print("Wrote docs/19b_advancement_effect_recovery.md")
print("Wrote cache/advancement_effect_recovery_stats.json")
