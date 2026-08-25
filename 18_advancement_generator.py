"""
18_advancement_generator.py

Constructs the advancement domain population.

WHY A CONSTRUCTED POPULATION EARNS ITS PLACE
============================================
No public individual level donor portfolio dataset is known to exist, and `08_sources.md`
carries that as an open claim. But the reason this domain is generated rather than found
is stronger than availability.

In OULAD and in MIMIC, true uplift is unobservable. Nobody was randomised, so the effect
of an advisor contact or a care management enrolment cannot be estimated from the data.
Every statement `08_allocation.py` and `17_mimic_allocation.py` make about effect ranking
is conditional on an efficacy model that was supplied. `17b` swept that assumption
continuously precisely because it could not be measured.

Here both counterfactuals exist by construction. y0 and y1 are generated for every
prospect, so the true individual treatment effect is known, and the allocation comparison
can be scored against ground truth rather than against an assumption.

    This is the only domain in the project where the question "how much does risk ranking
    actually cost" has an answer rather than a sensitivity range.

That is what the third domain contributes. It is not evidence about donors and nothing
here should ever be presented as such.

WHAT IS OBSERVED AND WHAT IS HIDDEN
===================================
The generator emits three layers.

    Features           what an advancement shop would have in its CRM
    Observed outcome   the gift that actually happened, under a historical visit policy
    Ground truth       y0, y1, the true effect, and the uplift group label

Only the first two may be used for fitting. The third is held back for scoring and every
downstream script asserts that it never enters a model. A leakage check runs here and is
repeated in `19`.

THE HISTORICAL POLICY IS CONFOUNDED ON PURPOSE
==============================================
Gift officers do not visit at random. They visit prospects with high capacity ratings and
strong giving histories, which are the same features that predict giving without a visit.
The generated policy reproduces that, so a model fitted on observed outcomes inherits the
confounding that a real CRM would carry.

A model that ignores this will read the effect of officer selection as the effect of the
visit. That is a real failure in advancement analytics and it is built in rather than
assumed away.

THE MECHANISM WAS DECLARED BEFORE THIS FILE EXISTED
===================================================
`docs/18_advancement_design.md` section 2 states the four group structure and the
direction of each effect, including the negative effect group, before any code was
written. Nothing here may deviate from it. The four groups:

    sure_thing      gives with or without a visit, effect near zero
    persuadable     gives only if visited, effect positive
    lost_cause      gives under neither, effect zero
    do_not_disturb  gives unless visited, effect NEGATIVE

The fourth group is what distinguishes this domain. Education and healthcare have no
established mechanism by which the intervention makes the outcome worse. Over
solicitation causing a loyal donor to lapse is recognised advancement practice.

PARAMETERS ARE ILLUSTRATIVE
===========================
Every value in the PARAMS block below is a placeholder. `08_sources.md` records the
advancement benchmarks as open. When they are filed, overwrite the block and rerun.
Nothing else changes, and the doc this script writes reprints the whole block so that any
figure produced from it can be traced to the parameters that produced it.

Until those values are sourced, no figure from this domain may appear in a public document
except as explicitly declared simulation.

Usage:
    python 18_advancement_generator.py

Writes:
    data/processed/advancement_population.parquet
    docs/18_advancement_generator.md
    cache/advancement_generator_stats.json
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

SEED = 20260823

# ---------------------------------------------------------------------------
# PARAMS. Illustrative placeholders. See 08_sources.md.
# ---------------------------------------------------------------------------

PARAMS = {
    "n_prospects": 50_000,
    "portfolio_size": 125,
    "n_officers": 12,

    "group_shares": {
        "sure_thing": 0.10,
        "persuadable": 0.16,
        "lost_cause": 0.66,
        "do_not_disturb": 0.08,
    },

    # baseline giving probability without a visit, by group
    "p0": {
        "sure_thing": 0.72,
        "persuadable": 0.06,
        "lost_cause": 0.02,
        "do_not_disturb": 0.55,
    },
    # giving probability if visited, by group
    "p1": {
        "sure_thing": 0.76,
        "persuadable": 0.34,
        "lost_cause": 0.03,
        "do_not_disturb": 0.38,
    },

    "gift_lognormal_mu": 7.4,
    "gift_lognormal_sigma": 1.5,
    "major_gift_threshold": 25_000,

    "historical_visit_rate": 0.06,
    "policy_capacity_weight": 2.2,
    "policy_history_weight": 1.6,
    "policy_noise": 0.8,

    "prior_donor_share": 0.38,
}

PARAM_SOURCE_STATUS = "ILLUSTRATIVE. All values open in 08_sources.md section Advancement."

GROUPS = ["sure_thing", "persuadable", "lost_cause", "do_not_disturb"]

GROUND_TRUTH_COLS = ["group", "y0", "y1", "tau", "p0", "p1",
                     "u_draw", "latent_capacity", "latent_affinity"]

stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


rng = np.random.default_rng(SEED)
n = PARAMS["n_prospects"]
t0 = time.time()

# ---------------------------------------------------------------------------
# Latent traits
# ---------------------------------------------------------------------------

capacity = rng.normal(0, 1, n)                      # wealth capacity, latent
affinity = rng.normal(0, 1, n)                      # institutional affinity, latent

is_prior_donor = rng.random(n) < PARAMS["prior_donor_share"]
prior_gift_count = np.where(
    is_prior_donor, rng.poisson(np.clip(2 + affinity, 0.2, None), n), 0
)
years_since_first = np.where(
    is_prior_donor, np.clip(rng.gamma(3, 3, n), 0.5, 45).round(1), 0.0
)
largest_gift = np.where(
    is_prior_donor,
    np.exp(rng.normal(
        PARAMS["gift_lognormal_mu"] + 0.6 * capacity,
        PARAMS["gift_lognormal_sigma"],
    )).round(0),
    0.0,
)
capacity_rating = np.clip((capacity * 1.5 + 5).round(0), 1, 9).astype(int)
event_attendance = rng.poisson(np.clip(0.8 + 0.7 * affinity, 0.05, None), n)
email_engagement = np.clip(rng.beta(2, 5, n) + 0.15 * affinity, 0, 1).round(3)
is_alum = rng.random(n) < 0.71
grad_decade = rng.choice([1970, 1980, 1990, 2000, 2010, 2020], n,
                         p=[0.06, 0.12, 0.19, 0.24, 0.25, 0.14])
region = rng.choice(["in_state", "adjacent", "national", "international"], n,
                    p=[0.44, 0.21, 0.31, 0.04])
is_volunteer = rng.random(n) < np.clip(0.05 + 0.06 * affinity, 0.005, 0.5)
spouse_is_alum = is_alum & (rng.random(n) < 0.22)

# ---------------------------------------------------------------------------
# Uplift group assignment, driven by the latents so it is partly learnable
# ---------------------------------------------------------------------------

score = 1.1 * affinity + 0.5 * capacity + 0.4 * is_prior_donor
logits = np.column_stack([
    1.6 * score - 1.9,                    # sure_thing, high affinity and history
    0.7 * score - 0.3 * capacity - 0.9,   # persuadable, movable middle
    -1.2 * score + 0.9,                   # lost_cause
    1.0 * score - 0.8 * affinity - 1.7,   # do_not_disturb, gives but resents contact
])
logits += rng.gumbel(0, 1, logits.shape)

shares = np.array([PARAMS["group_shares"][g] for g in GROUPS])
offsets = np.zeros(4)
for _ in range(400):                       # calibrate offsets to hit target shares
    pick = np.argmax(logits + offsets, axis=1)
    obs = np.array([(pick == i).mean() for i in range(4)])
    offsets += 0.6 * (shares - obs) / np.maximum(shares, 1e-3)
group_idx = np.argmax(logits + offsets, axis=1)
group = np.array(GROUPS)[group_idx]

# ---------------------------------------------------------------------------
# Potential outcomes
# ---------------------------------------------------------------------------

p0 = np.array([PARAMS["p0"][g] for g in group])
p1 = np.array([PARAMS["p1"][g] for g in group])

# within group heterogeneity so the truth is not four constants
jitter = np.clip(0.10 * capacity + 0.08 * affinity, -0.35, 0.35)
p0 = np.clip(p0 * (1 + jitter), 0.001, 0.999)
p1 = np.clip(p1 * (1 + jitter), 0.001, 0.999)

u = rng.random(n)                          # common uniform, so y0 and y1 are coupled
y0 = (u < p0).astype(int)
y1 = (u < p1).astype(int)
tau = p1 - p0

# ---------------------------------------------------------------------------
# Historical visit policy, deliberately confounded
# ---------------------------------------------------------------------------

policy_score = (
    PARAMS["policy_capacity_weight"] * (capacity_rating - 5) / 4
    + PARAMS["policy_history_weight"] * np.log1p(largest_gift) / 12
    + PARAMS["policy_noise"] * rng.normal(0, 1, n)
)
cut = np.quantile(policy_score, 1 - PARAMS["historical_visit_rate"])
visited = (policy_score >= cut).astype(int)

y_obs = np.where(visited == 1, y1, y0)

gift_amount = np.where(
    y_obs == 1,
    np.exp(rng.normal(
        PARAMS["gift_lognormal_mu"] + 0.8 * capacity,
        PARAMS["gift_lognormal_sigma"],
    )).round(0),
    0.0,
)
is_major = (gift_amount >= PARAMS["major_gift_threshold"]).astype(int)

# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------

df = pd.DataFrame({
    "prospect_id": np.arange(1, n + 1),
    "is_prior_donor": is_prior_donor.astype(int),
    "prior_gift_count": prior_gift_count,
    "years_since_first_gift": years_since_first,
    "largest_gift": largest_gift,
    "capacity_rating": capacity_rating,
    "event_attendance": event_attendance,
    "email_engagement": email_engagement,
    "is_alum": is_alum.astype(int),
    "grad_decade": grad_decade,
    "region": region,
    "is_volunteer": is_volunteer.astype(int),
    "spouse_is_alum": spouse_is_alum.astype(int),
    "visited": visited,
    "gave": y_obs,
    "gift_amount": gift_amount,
    "is_major_gift": is_major,
    # ground truth, never a feature
    "group": group,
    "y0": y0,
    "y1": y1,
    "tau": tau.round(6),
    "p0": p0.round(6),
    "p1": p1.round(6),
    # retained so 22 can sweep without a second generator
    "u_draw": u,
    "latent_capacity": capacity,
    "latent_affinity": affinity,
})

assert len(df) == n
assert set(GROUND_TRUTH_COLS).issubset(df.columns)
assert df["gave"].equals(
    pd.Series(np.where(df["visited"] == 1, df["y1"], df["y0"]))
), "observed outcome must equal the potential outcome under the assigned arm"
assert ((df["gift_amount"] > 0) == (df["gave"] == 1)).all(), "gift only when gave"

PROC.mkdir(parents=True, exist_ok=True)
df.to_parquet(PROC / "advancement_population.parquet", index=False)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

w("# 18. Advancement population")
w()
w("Generated by `18_advancement_generator.py`. Do not edit by hand.")
w()
w(
    "Constructed, not observed. Nothing in this document is evidence about donors. The "
    "population exists so that the allocation comparison can be scored against a known "
    "true effect, which is impossible in the education and clinical domains because "
    "nobody in either was randomised."
)
w()
w(f"**Parameter status: {PARAM_SOURCE_STATUS}**")
w()
w("## Parameters")
w()
w("```json")
w(json.dumps(PARAMS, indent=2))
w("```")
w()
w(
    "Every figure below is a consequence of the block above. When `08_sources.md` closes "
    "the advancement benchmarks, overwrite the block and rerun. No structure changes."
)
w()

w("## Population")
w()
w("| Quantity | Value |")
w("|---|---:|")
w(f"| Prospects | {n:,} |")
w(f"| Prior donors | {df['is_prior_donor'].sum():,} ({df['is_prior_donor'].mean():.1%}) |")
w(f"| Visited under the historical policy | {df['visited'].sum():,} ({df['visited'].mean():.1%}) |")
w(f"| Gave | {df['gave'].sum():,} ({df['gave'].mean():.1%}) |")
w(f"| Major gifts | {df['is_major_gift'].sum():,} |")
w(f"| Total raised | ${df['gift_amount'].sum():,.0f} |")
w(f"| Officers modelled | {PARAMS['n_officers']} |")
w(f"| Portfolio capacity | {PARAMS['n_officers'] * PARAMS['portfolio_size']:,} "
  f"({PARAMS['n_officers'] * PARAMS['portfolio_size'] / n:.2%} of the pool) |")
w()

w("## The four groups")
w()
w(
    "Declared in `docs/18_advancement_design.md` section 2 before this script existed. "
    "The effect column is the true mean individual effect, available here and nowhere "
    "else in the project."
)
w()
w("| Group | Share | Mean p0 | Mean p1 | Mean true effect | Visited under policy |")
w("|---|---:|---:|---:|---:|---:|")
for g in GROUPS:
    m = df["group"] == g
    w(
        f"| {g} | {m.mean():.1%} | {df.loc[m, 'p0'].mean():.3f} | "
        f"{df.loc[m, 'p1'].mean():.3f} | {df.loc[m, 'tau'].mean():+.3f} | "
        f"{df.loc[m, 'visited'].mean():.1%} |"
    )
w()
w(
    f"The do not disturb group carries a negative mean effect of "
    f"{df.loc[df['group'] == 'do_not_disturb', 'tau'].mean():+.3f}. No other domain in "
    "this project has a group for whom the intervention is actively harmful, and its "
    "presence is the reason risk ranking can be worse than useless here rather than "
    "merely inefficient."
)
w()

w("## The historical policy is confounded")
w()
w(
    "Officers visited on capacity rating and giving history, which also predict giving "
    "without a visit. A naive comparison of visited against not visited therefore "
    "attributes officer selection to the visit."
)
w()
naive = df.loc[df["visited"] == 1, "gave"].mean() - df.loc[df["visited"] == 0, "gave"].mean()
truth = df["tau"].mean()
w("| Quantity | Value |")
w("|---|---:|")
w(f"| Naive visited minus not visited | {naive:+.4f} |")
w(f"| True average effect | {truth:+.4f} |")
w(f"| Confounding bias | {naive - truth:+.4f} |")
w()
w(
    "A shop reading the naive figure would overstate the value of a visit by "
    f"{abs(naive - truth) / abs(truth):.0%} of its true size. This is generated on "
    "purpose. It is the error the domain exists to make visible."
)
w()

w("## Where the true effect sits against baseline probability")
w()
w(
    "The allocation question in one table. If effect rose with baseline probability, risk "
    "ranking would be correct and this project would have nothing to say."
)
w()
w("| Decile of p0 | N | Mean p0 | Mean true effect | Negative effect share |")
w("|---:|---:|---:|---:|---:|")
dec = pd.qcut(df["p0"], 10, labels=False, duplicates="drop")
for d in sorted(pd.unique(dec)):
    m = dec == d
    w(
        f"| {d + 1} | {int(m.sum()):,} | {df.loc[m, 'p0'].mean():.3f} | "
        f"{df.loc[m, 'tau'].mean():+.4f} | {(df.loc[m, 'tau'] < 0).mean():.1%} |"
    )
w()

w("## Leakage guard")
w()
w(
    "These columns are ground truth and must never enter a model. `19` repeats this "
    "assertion and every later script drops them by name."
)
w()
w("```")
w(", ".join(GROUND_TRUTH_COLS))
w("```")
w()

w("## What this population cannot support")
w()
w(
    "It cannot support any claim about real donors, real conversion rates, or real "
    "response to contact. The four group structure is asserted, not measured. The "
    "parameters are placeholders. Any public reference to this domain is framed as "
    "simulation."
)
w()

stats["params"] = PARAMS
stats["param_source_status"] = PARAM_SOURCE_STATUS
stats["seed"] = SEED
stats["n"] = int(n)
stats["gave_rate"] = float(df["gave"].mean())
stats["visit_rate"] = float(df["visited"].mean())
stats["true_ate"] = float(truth)
stats["naive_ate"] = float(naive)
stats["confounding_bias"] = float(naive - truth)
stats["group_shares"] = {g: float((df["group"] == g).mean()) for g in GROUPS}
stats["group_true_effect"] = {
    g: float(df.loc[df["group"] == g, "tau"].mean()) for g in GROUPS
}
stats["negative_effect_share"] = float((df["tau"] < 0).mean())
stats["runtime_seconds"] = round(time.time() - t0, 1)

DOCS.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
(DOCS / "18_advancement_generator.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "advancement_generator_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.1f}s")
print("Wrote data/processed/advancement_population.parquet")
print("Wrote docs/18_advancement_generator.md")
print("Wrote cache/advancement_generator_stats.json")
