"""
21_advancement_allocation.py

The central advancement analysis. Four allocation strategies under a capacity constraint,
every one of them scored against the true counterfactual outcomes `18` retained.

WHY THIS SCRIPT CAN DO WHAT THE OTHER DOMAINS COULD NOT
=======================================================
`08_allocation.py` and `17_mimic_allocation.py` compared risk ranking against effect
ranking under efficacy models that were supplied rather than measured, because nobody in
OULAD or MIMIC was randomised. `17b` swept the assumption continuously for exactly that
reason.

Here y0 and y1 exist for every prospect. Each strategy can be scored on what it would
actually have achieved, and an oracle that ranks on true individual effect provides the
ceiling. The gap between a deployable strategy and that ceiling is the quantity the other
two domains can only bound.

THE FOUR STRATEGIES
===================
    historical   what the shop already does. Ranked by estimated propensity to be
                 visited, fitted out of fold on observable features, which reproduces the
                 selection logic `18` used without granting access to the policy score.

    risk         ranked by estimated probability of giving without a visit. This is what
                 a conventional predictive system produces and what most shops deploy.

    effect       ranked by estimated incremental effect of a visit, from the T learner
                 that `19b` found best among observational estimators at correlation
                 0.1938 with true effect.

    oracle       ranked by true individual effect. NOT DEPLOYABLE. It consumes ground
                 truth that no institution could ever have. It exists only to bound what
                 any method could achieve, and no recommendation may rest on it.

THE PRIMARY METRIC IS DECLARED BEFORE THE RESULTS
=================================================
    Expected incremental gifts, the sum of true individual effect over the selected set.

That is the quantity a capacity constrained programme exists to maximise: how many more
gifts happen because of the visits, not how many gifts the selected prospects make. A
strategy that selects prospects who would have given anyway scores highly on gifts and
zero on this.

Realised incremental gifts, the sum of y1 minus y0 over the selected set, is reported
alongside. It is the same quantity subject to the coin flips `18` drew, so it is noisier
and reflects one particular realisation.

Harm is reported separately and is not netted into the primary metric, because a programme
that averts twenty gifts and destroys ten is not equivalent to one that averts ten and
destroys none, even though the arithmetic matches.

DOLLARS ARE NOT IDENTIFIED HERE
===============================
`18` generates `gift_amount` only for the arm each prospect actually received. There is no
amount under the counterfactual arm, so incremental dollars cannot be computed without
inventing a value. Gift counts are reported instead and the limitation is stated rather
than papered over. Extending `18` to draw amounts under both arms would close this and is
recorded as an open item rather than done silently here.

EQUITY IS DISCLOSED BEFORE THE SUMMARY
======================================
Composition of the selected set under every strategy, by true group and by observable
attributes, with representation relative to the population. Do not disturb exposure is
called out explicitly. The movement is described. Whether it is acceptable is a policy
judgment this script does not make.

Usage:
    python 21_advancement_allocation.py

Reads:
    data/processed/advancement_population.parquet
    data/processed/advancement_risk_oof.parquet

Writes:
    docs/21_advancement_allocation.md
    cache/advancement_allocation_stats.json
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

CAPACITIES = [0.01, 0.03, 0.05, 0.10, 0.20]
HEADLINE_CAPACITY = 0.03
PRIMARY_METRIC = "expected incremental gifts"

GROUND_TRUTH = ["group", "y0", "y1", "tau", "p0", "p1",
                "u_draw", "latent_capacity", "latent_affinity"]
OUTCOME_DERIVED = ["gift_amount", "is_major_gift"]
OUTCOME, TREATMENT, ID = "gave", "visited", "prospect_id"
CATEGORICAL = ["region", "grad_decade"]

GROUPS = ["sure_thing", "persuadable", "lost_cause", "do_not_disturb"]
STRATEGIES = ["historical", "risk", "effect", "oracle"]
DEPLOYABLE = {"historical": True, "risk": True, "effect": True, "oracle": False}

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


t0 = time.time()
pop = pd.read_parquet(PROC / "advancement_population.parquet")
oof = pd.read_parquet(PROC / "advancement_risk_oof.parquet")
df = pop.merge(oof.drop(columns=[OUTCOME, TREATMENT]), on=ID, how="inner")
assert len(df) == len(pop), "merge must preserve the population"
n = len(df)

FEATURES = [
    c for c in pop.columns
    if c not in GROUND_TRUTH + OUTCOME_DERIVED + [OUTCOME, ID, TREATMENT]
]
base = pd.get_dummies(df[FEATURES], columns=CATEGORICAL, drop_first=True).astype(float)
D = StandardScaler().fit_transform(base.to_numpy())

y0 = df["y0"].to_numpy()
y1 = df["y1"].to_numpy()
tau = df["tau"].to_numpy()
group = df["group"].to_numpy()
v_hist = df[TREATMENT].to_numpy()
folds = df["fold"].to_numpy()

# historical propensity, fitted out of fold on observables only
prop = np.full(n, np.nan)
for f in range(N_FOLDS):
    tr, te = folds != f, folds == f
    m = LogisticRegression(max_iter=3000, solver="lbfgs").fit(D[tr], v_hist[tr])
    prop[te] = m.predict_proba(D[te])[:, 1]
assert not np.isnan(prop).any()

scores = {
    "historical": prop,
    "risk": df["logit_p0_s"].to_numpy(),
    "effect": df["logit_tau_t"].to_numpy(),
    "oracle": tau,
}

baseline_gifts = int(y0.sum())
results = {}

for cap in CAPACITIES:
    k = max(1, int(round(cap * n)))
    sel = {s: top_k(scores[s], k) for s in STRATEGIES}
    cell = {"k": int(k), "capacity": cap, "strategies": {}, "overlap": {}}

    for s in STRATEGIES:
        idx = sel[s]
        mask = np.zeros(n, dtype=bool)
        mask[idx] = True
        total_gifts = int(y1[mask].sum() + y0[~mask].sum())
        cell["strategies"][s] = {
            "deployable": DEPLOYABLE[s],
            "selected_n": int(k),
            "gifts_if_all_untreated": baseline_gifts,
            "total_gifts": total_gifts,
            "realised_incremental": int(total_gifts - baseline_gifts),
            "expected_incremental": float(tau[idx].sum()),
            "mean_true_effect": float(tau[idx].mean()),
            "harmed_n": int((tau[idx] < 0).sum()),
            "harm_share": float((tau[idx] < 0).mean()),
            "realised_harm_n": int(((y0[idx] == 1) & (y1[idx] == 0)).sum()),
            "dnd_share": float((group[idx] == "do_not_disturb").mean()),
            "group_shares": {g: float((group[idx] == g).mean()) for g in GROUPS},
        }

    orc = cell["strategies"]["oracle"]["expected_incremental"]
    for s in STRATEGIES:
        e = cell["strategies"][s]["expected_incremental"]
        cell["strategies"][s]["regret_vs_oracle"] = float(orc - e)
        cell["strategies"][s]["effect_captured"] = float(e / orc) if orc else np.nan

    for a in STRATEGIES:
        for b in STRATEGIES:
            if a < b:
                cell["overlap"][f"{a}|{b}"] = float(jaccard(sel[a], sel[b]))

    results[f"{cap:.2f}"] = cell

cap_key = f"{HEADLINE_CAPACITY:.2f}"
head = results[cap_key]
k_head = head["k"]
sel_head = {s: top_k(scores[s], k_head) for s in STRATEGIES}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

w("# 21. Advancement allocation")
w()
w("Generated by `21_advancement_allocation.py`. Do not edit by hand.")
w()
w(
    "Simulation. Every strategy is scored against the true counterfactual outcomes `18` "
    "retained, which is possible in this domain and in neither of the other two."
)
w()
w(f"**Primary metric: {PRIMARY_METRIC}.** The sum of true individual effect over the "
  "selected set. Declared before results. A strategy that selects prospects who would "
  "have given anyway scores highly on total gifts and near zero on this.")
w()
w("## The four strategies")
w()
w("| Strategy | Ranked by | Deployable |")
w("|---|---|---|")
w("| historical | estimated propensity to be visited, out of fold | yes |")
w("| risk | estimated probability of giving without a visit | yes |")
w("| effect | estimated incremental effect, T learner | yes |")
w("| oracle | true individual effect | **no** |")
w()
w(
    "The oracle consumes ground truth no institution could have. It bounds what any method "
    "could achieve. No recommendation may rest on it."
)
w()

w(f"## Results at the operational capacity, {HEADLINE_CAPACITY:.0%}")
w()
w(f"{k_head:,} prospects of {n:,}. Baseline gifts with nobody visited: "
  f"{baseline_gifts:,}.")
w()
w("| Strategy | Expected incremental | Realised incremental | Mean true effect | "
  "Effect captured | Regret |")
w("|---|---:|---:|---:|---:|---:|")
for s in STRATEGIES:
    d = head["strategies"][s]
    w(
        f"| {s} | {d['expected_incremental']:+.1f} | {d['realised_incremental']:+d} | "
        f"{d['mean_true_effect']:+.4f} | {d['effect_captured']:.1%} | "
        f"{d['regret_vs_oracle']:.1f} |"
    )
w()

w("## Harm")
w()
w(
    "Reported separately and never netted into the primary metric. A programme that averts "
    "twenty gifts and destroys ten is not equivalent to one that averts ten and destroys "
    "none."
)
w()
w("| Strategy | Prospects with negative true effect | Share | Realised losses | DND share |")
w("|---|---:|---:|---:|---:|")
for s in STRATEGIES:
    d = head["strategies"][s]
    w(
        f"| {s} | {d['harmed_n']:,} | {d['harm_share']:.1%} | "
        f"{d['realised_harm_n']:,} | {d['dnd_share']:.1%} |"
    )
w()

w("## How much do the strategies overlap?")
w()
w("| Pair | Jaccard |")
w("|---|---:|")
for pair, val in head["overlap"].items():
    w(f"| {pair.replace('|', ' against ')} | {val:.3f} |")
w()

w("## Across capacity")
w()
w("| Capacity | k | " + " | ".join(STRATEGIES) + " |")
w("|---|---:|" + "---:|" * len(STRATEGIES))
for cap in CAPACITIES:
    c = results[f"{cap:.2f}"]
    vals = " | ".join(
        f"{c['strategies'][s]['expected_incremental']:+.1f}" for s in STRATEGIES
    )
    w(f"| {cap:.0%} | {c['k']:,} | {vals} |")
w()
w("Effect captured against the oracle at each capacity.")
w()
w("| Capacity | " + " | ".join(s for s in STRATEGIES if DEPLOYABLE[s]) + " |")
w("|---|" + "---:|" * sum(DEPLOYABLE.values()))
for cap in CAPACITIES:
    c = results[f"{cap:.2f}"]
    vals = " | ".join(
        f"{c['strategies'][s]['effect_captured']:.1%}"
        for s in STRATEGIES if DEPLOYABLE[s]
    )
    w(f"| {cap:.0%} | {vals} |")
w()

w("## Who each strategy selects")
w()
w(
    "Composition by true group. Representation is the selected share divided by the "
    "population share, so 1.00 is proportional. The movement is described here. Whether it "
    "is acceptable is a policy judgment this script does not make."
)
w()
pop_share = {g: float((group == g).mean()) for g in GROUPS}
w("| Group | Population | " + " | ".join(STRATEGIES) + " |")
w("|---|---:|" + "---:|" * len(STRATEGIES))
for g in GROUPS:
    cells = " | ".join(
        f"{head['strategies'][s]['group_shares'][g]:.1%}" for s in STRATEGIES
    )
    w(f"| {g} | {pop_share[g]:.1%} | {cells} |")
w()
w("Representation relative to population.")
w()
w("| Group | " + " | ".join(STRATEGIES) + " |")
w("|---|" + "---:|" * len(STRATEGIES))
for g in GROUPS:
    cells = " | ".join(
        f"{head['strategies'][s]['group_shares'][g] / pop_share[g]:.2f}"
        if pop_share[g] > 0 else "n/a"
        for s in STRATEGIES
    )
    w(f"| {g} | {cells} |")
w()

w("## Composition by observable attribute")
w()
equity = {}
for attr in ["region", "is_alum", "is_prior_donor", "capacity_rating"]:
    if attr not in df.columns:
        continue
    col = df[attr].astype(str).to_numpy()
    levels = sorted(pd.unique(col))
    if len(levels) > 9:
        continue
    w(f"**{attr}**")
    w()
    w("| Level | Population | " + " | ".join(STRATEGIES) + " |")
    w("|---|---:|" + "---:|" * len(STRATEGIES))
    equity[attr] = {}
    for lv in levels:
        popshare = float((col == lv).mean())
        row = {"population": popshare}
        cells = []
        for s in STRATEGIES:
            sh = float((col[sel_head[s]] == lv).mean())
            row[s] = sh
            cells.append(f"{sh:.1%}")
        equity[attr][lv] = row
        w(f"| {lv} | {popshare:.1%} | " + " | ".join(cells) + " |")
    w()

w("## Limitations")
w()
w(
    "Dollars are not identified. `18` generates `gift_amount` only for the arm each "
    "prospect actually received, so incremental dollars cannot be computed without "
    "inventing a counterfactual amount. Gift counts are reported instead. Extending `18` "
    "to draw amounts under both arms would close this and is recorded as open."
)
w()
w(
    "The oracle is not achievable. `19b` established that the observable features explain "
    "under five percent of the variance in true effect, so the oracle row is a bound on "
    "the value of better information, not a target any method can reach."
)
w()
w(
    "`20` found the effect ranking not usable on stability grounds at Jaccard 0.240 with a "
    "core of 0.047. Any value the effect strategy shows here is delivered by a list that "
    "would substantially change on a refit."
)
w()
w(
    "All parameters remain illustrative and open in `08_sources.md`. Nothing here is "
    "evidence about real donors."
)
w()

stats["seed"] = SEED
stats["n"] = int(n)
stats["primary_metric"] = PRIMARY_METRIC
stats["capacities"] = CAPACITIES
stats["headline_capacity"] = HEADLINE_CAPACITY
stats["baseline_gifts"] = baseline_gifts
stats["strategies"] = STRATEGIES
stats["deployable"] = DEPLOYABLE
stats["population_group_shares"] = pop_share
stats["results"] = results
stats["equity_observable"] = equity
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "21_advancement_allocation.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "advancement_allocation_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.1f}s")
print("Wrote docs/21_advancement_allocation.md")
print("Wrote cache/advancement_allocation_stats.json")
