"""
06b_education_roster.py

Exports which students each approach would actually contact, so the site can show the
allocation rather than describe it.

`06_allocation.py` reports overlap and value gap as averages across cohorts and
replications. Averages cannot be looked at. This script reruns the same procedure for one
cohort at each decision point and records, student by student, who lands on each list.

NOTHING NEW IS ESTIMATED
========================
Same estimator, same three way split, same efficacy family, same seeding scheme as
`06_allocation.py`. This is that analysis with the selections written down instead of
summarised. `06` is not modified and its outputs do not change.

WHAT MAKES THIS DOMAIN DIFFERENT
================================
Education is the only domain here with a noise floor built into the design: two models
trained on different halves of the same cohort, ranking the same held out students. The
disagreement between those two is the disagreement you get from nothing more than which
half of the history you happened to see.

So three lists are exported, not two:

    analyst A     one risk model's top k
    analyst B     a second risk model, same method, different half of the history
    effect        the effect ranking derived from analyst A's own predictions

A reader can see that two people doing the same job already disagree, before any argument
about risk against effect begins. That comparison requires no assumption at all, which
makes it the strongest thing this domain has to show.

ONE COHORT, FOLLOWED THROUGH TIME
=================================
The same cohort is used at every decision point so the reader steps through day 0 to day
84 watching one group of students, not four unrelated groups. The cohort is the largest
one present at all four days, chosen by size before any result is computed.

Replication 0 only. `06` averages over ten; this shows one, and says so.

Usage:
    python 06b_education_roster.py

Reads:
    data/processed/features_d{D}.parquet

Writes:
    cache/education_roster.json
    docs/06b_education_roster.md
"""

import hashlib
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

DECISION_DAYS = [0, 28, 56, 84]
CAPACITY_PCT = [0.01, 0.02, 0.05, 0.10, 0.20]
GAMMAS = [0.0, 1.0, 2.0, 3.0]
HEADLINE_GAMMA = 2.0
HEADLINE_CAPACITY = 0.10
ATE_TARGET = 0.05
MIN_COHORT = 1500
REPLICATION = 0
SEED = 20260821
ROSTER_MAX = 1200

CATEGORICAL = ["gender", "region", "highest_education", "imd_band", "age_band", "disability"]
DROP = ["id_student", "fold", "outcome", "code_module", "code_presentation"]
EQUITY = ["imd_band", "highest_education", "age_band", "disability", "gender"]

LISTS = ["analyst_a", "analyst_b", "effect"]

lines = []


def w(s=""):
    lines.append(s)
    print(s)


def seed_for(*parts):
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big")


def topk_idx(x, k):
    return np.argsort(-x, kind="stable")[:k]


def tau_of_r(r, gamma, ate):
    shape = r * (1.0 - r) ** gamma
    m = shape.mean()
    return shape * (ate / m) if m > 0 else np.zeros_like(shape)


def fit(Xtr, ytr, Xte, cats, nums):
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), cats),
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), nums),
    ])
    pipe = make_pipeline(pre, LogisticRegression(max_iter=2000))
    pipe.fit(Xtr, ytr)
    return pipe.predict_proba(Xte)[:, 1]


t0 = time.time()

# ---------------------------------------------------------------------------
# Choose one cohort present at every decision point, largest first
# ---------------------------------------------------------------------------

present = None
sizes_at = {}
for D in DECISION_DAYS:
    feat = pd.read_parquet(PROC / f"features_d{D}.parquet")
    s = feat.groupby(["code_module", "code_presentation"]).size()
    s = s[s >= MIN_COHORT]
    sizes_at[D] = s
    keys = set(s.index)
    present = keys if present is None else (present & keys)

if not present:
    raise SystemExit("No cohort clears the minimum size at every decision point.")

cohort = max(present, key=lambda mp: int(sizes_at[DECISION_DAYS[0]][mp]))
label = f"{cohort[0]} {cohort[1]}"
print(f"cohort {label}")

days = {}

for D in DECISION_DAYS:
    feat = pd.read_parquet(PROC / f"features_d{D}.parquet")
    sub = feat[
        (feat["code_module"] == cohort[0]) & (feat["code_presentation"] == cohort[1])
    ].reset_index(drop=True)

    cols = [c for c in sub.columns if c not in DROP]
    cats = [c for c in CATEGORICAL if c in cols]
    nums = [c for c in cols if c not in cats]
    X, y = sub[cols], sub["outcome"].to_numpy()
    n = len(sub)

    rng = np.random.default_rng(seed_for(SEED, D, cohort[0], cohort[1], REPLICATION))
    a, b, c = np.array_split(rng.permutation(n), 3)
    yc = y[c]
    if not (0 < yc.sum() < len(yc)):
        raise SystemExit(f"Evaluation part at day {D} has no outcome variation.")

    ra = fit(X.iloc[a], y[a], X.iloc[c], cats, nums)
    rb = fit(X.iloc[b], y[b], X.iloc[c], cats, nums)
    auc = float(roc_auc_score(yc, ra))

    # sample down only if the evaluation part is larger than the field can show
    order = np.arange(len(c))
    if len(order) > ROSTER_MAX:
        srng = np.random.default_rng(seed_for("sample", SEED, D))
        order = np.sort(srng.choice(order, size=ROSTER_MAX, replace=False))

    eq = {}
    for col in EQUITY:
        if col not in sub.columns:
            continue
        # cast element by element: a column can hold band labels alongside NaN, and a
        # mixed float/str array cannot be sorted
        vals = [
            "not recorded" if pd.isna(v) else str(v)
            for v in sub[col].to_numpy()[c][order]
        ]
        levels = sorted(set(vals))
        if len(levels) <= 12:
            eq[col] = {"levels": levels, "index": [levels.index(v) for v in vals]}

    caps = {}
    for p in CAPACITY_PCT:
        k = max(1, int(round(p * len(c))))
        sel = {"analyst_a": topk_idx(ra, k), "analyst_b": topk_idx(rb, k)}
        per_gamma = {}
        for g in GAMMAS:
            sel_e = topk_idx(tau_of_r(ra, g, ATE_TARGET), k)
            per_gamma[f"{g:.1f}"] = sel_e
        # headline effect list drives the mask; other gammas kept as overlap only
        sel["effect"] = per_gamma[f"{HEADLINE_GAMMA:.1f}"]

        masks = []
        for j in order:
            mbits = 0
            for bpos, name in enumerate(LISTS):
                if j in sel[name]:
                    mbits |= (1 << bpos)
            masks.append(mbits)

        def ov(u, v):
            su, sv = set(u.tolist()), set(v.tolist())
            return len(su & sv) / len(su | sv) if (su | sv) else float("nan")

        caps[f"{p:.2f}"] = {
            "k": int(k),
            "n_eval": int(len(c)),
            "n_sampled": int(len(order)),
            "mask": masks,
            "withdrew": [int(x) for x in yc[order]],
            "noise_floor": float(ov(sel["analyst_a"], sel["analyst_b"])),
            "risk_vs_effect": float(ov(sel["analyst_a"], sel["effect"])),
            "overlap_by_gamma": {
                g: float(ov(sel["analyst_a"], idx)) for g, idx in per_gamma.items()
            },
        }

    days[str(D)] = {
        "day": D, "auc": auc, "n_cohort": int(n),
        "withdrawal_rate": float(y.mean()),
        "equity": eq, "capacities": caps,
    }
    print(f"  day {D}: auc {auc:.3f}, {len(c)} evaluated ({time.time() - t0:.0f}s)")

roster = {
    "cohort": label,
    "lists": LISTS,
    "list_labels": {
        "analyst_a": "One analyst's list",
        "analyst_b": "A second analyst, same method",
        "effect": "Ranked by who a contact would change",
    },
    "decision_days": DECISION_DAYS,
    "capacities": CAPACITY_PCT,
    "headline_capacity": HEADLINE_CAPACITY,
    "headline_gamma": HEADLINE_GAMMA,
    "gammas": GAMMAS,
    "replication": REPLICATION,
    "note": (
        "One cohort followed across all four decision points, single replication. "
        "`06_allocation.py` averages across cohorts and replications; this shows one so "
        "the selections can be seen rather than summarised."
    ),
    "days": days,
}
CACHE.mkdir(parents=True, exist_ok=True)
(CACHE / "education_roster.json").write_text(json.dumps(roster), encoding="utf-8")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

hk = f"{HEADLINE_CAPACITY:.2f}"

w("# 06b. Education roster")
w()
w("Generated by `06b_education_roster.py`. Do not edit by hand.")
w()
w(
    f"Cohort `{label}`, replication {REPLICATION}, followed across all four decision "
    "points. Same estimator, split and efficacy family as `06_allocation.py`. Nothing "
    "new is estimated and `06` is unmodified."
)
w()

w("## Two analysts, same method, different halves")
w()
w(
    "The overlap between two risk models trained on different thirds of the same cohort, "
    "ranking students neither has seen. This is disagreement from nothing but which half "
    "of the history each one saw."
)
w()
w("| Day | Students evaluated | AUC | " + " | ".join(f"{p:.0%}" for p in CAPACITY_PCT) + " |")
w("|---:|---:|---:|" + "---:|" * len(CAPACITY_PCT))
for D in DECISION_DAYS:
    d = days[str(D)]
    cells = " | ".join(
        f"{d['capacities'][f'{p:.2f}']['noise_floor']:.2f}" for p in CAPACITY_PCT
    )
    w(f"| {D} | {d['capacities'][hk]['n_eval']:,} | {d['auc']:.3f} | {cells} |")
w()

w("## Does waiting for more information help?")
w()
w(
    "AUC at each decision point for the same cohort. Day 0 knows only who registered. "
    "Day 84 has twelve weeks of behaviour."
)
w()
w("| Day | AUC | Change from day 0 |")
w("|---:|---:|---:|")
base = days[str(DECISION_DAYS[0])]["auc"]
for D in DECISION_DAYS:
    d = days[str(D)]
    w(f"| {D} | {d['auc']:.4f} | {d['auc'] - base:+.4f} |")
w()

w("## Risk against effect, at the headline capacity")
w()
w(f"Capacity {HEADLINE_CAPACITY:.0%}, gamma {HEADLINE_GAMMA:.1f}. Compare each row "
  "against its own noise floor above; an overlap higher than the floor means the two "
  "rankings disagree less than two analysts do.")
w()
w("| Day | Noise floor | Risk against effect | Clears the floor |")
w("|---:|---:|---:|---|")
for D in DECISION_DAYS:
    c = days[str(D)]["capacities"][hk]
    w(f"| {D} | {c['noise_floor']:.3f} | {c['risk_vs_effect']:.3f} | "
      f"{'yes' if c['risk_vs_effect'] < c['noise_floor'] else 'no'} |")
w()

w("## Limitations")
w()
w(
    "One cohort and one replication, chosen by size before any result was computed. The "
    "averages in `06_allocation.py` remain the reportable figures; this exists so the "
    "selections can be shown. Efficacy is assumed rather than measured, as it is "
    "everywhere in this domain."
)
w()

DOCS.mkdir(parents=True, exist_ok=True)
(DOCS / "06b_education_roster.md").write_text("\n".join(lines), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.1f}s")
print("Wrote cache/education_roster.json")
print("Wrote docs/06b_education_roster.md")
