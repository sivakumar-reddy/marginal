"""
17_mimic_allocation.py

The comparison the project exists to make, on the clinical domain.

A capacity constrained programme cannot treat everyone. The conventional move is to rank
by predicted risk and take the top k. That is optimal only if the benefit of treating
someone is proportional to their risk. If benefit varies with baseline risk in any other
way, the ranking that maximises outcomes averted is a different ranking, and the two lists
name different people.

`14` produced the risk model. `15` chose logistic regression on stability grounds. `16`
established that the ordering transfers to an unseen service while the level does not.
This script takes those predictions and asks what the capacity constraint does with them.

NO REFITTING
============
Everything here is post processing on `data/processed/mimic_risk_oof.parquet`. Nothing is
fitted. The script runs in minutes, not hours.

THE EFFICACY MODELS ARE ASSUMPTIONS, NOT FINDINGS
=================================================
MIMIC contains no randomised intervention. There is no readmission reduction trial in this
data and none is claimed. Absolute risk reduction as a function of baseline risk is
therefore supplied rather than estimated, from a pre registered family:

    ARR(p) = k * p^alpha * (1 - p)^beta

    E1  proportional        alpha 1, beta 0    ARR rises linearly with risk
    E2  mild attenuation    alpha 1, beta 1    benefit peaks at p = 0.50
    E3  strong attenuation  alpha 1, beta 3    benefit peaks at p = 0.25
    E4  ceiling             ARR = min(c, k*p)  benefit saturates above a threshold

E1 is the null case for this whole comparison. Under proportional benefit the effect
ranking is a monotone transform of the risk ranking and the two lists are identical by
construction. It is included precisely so that the divergence reported for E2, E3 and E4
can be read against a case where zero divergence is guaranteed. If E1 shows any
divergence, this script has a bug.

E2 and E3 encode a clinical intuition that is plausible and unverified: readmissions among
the very highest risk patients are driven by disease severity and are less preventable by
a care management programme, so benefit peaks somewhere below the top of the risk
distribution. E4 encodes a programme whose benefit saturates.

None of these is measured. The deliverable is the map from assumption to allocation, not a
claim about which assumption holds. A reader who believes benefit is proportional should
read E1 and conclude that risk ranking is correct for them.

THREE CONFIGURATIONS
====================
`16` found level failing in 110 of 136 service cells, so a pooled allocation on raw
predictions is known to be miscalibrated between services. All three are reported because
the interesting result is likely that none is clean.

    pooled_raw       one ranked list across all services, predictions as fitted
    pooled_recal     one ranked list, each service intercept shifted so mean predicted
                     equals that service's base rate
    within_service   capacity split across services in proportion to service size, each
                     service ranked separately

Intercept only recalibration is a monotone transform inside a service, so it cannot change
the within service ordering. Any difference between `pooled_raw` and `pooled_recal` is
therefore purely a re weighting between services, which is exactly what `16` broke.

The recalibration offset is computed on the observed base rate of the service, which a
hospital knows without any modelling. It is not fitted on the outcomes being predicted in
any way that could leak, but it does use the realised rate of the same slice, and that is
stated as a limitation rather than hidden.

PRE REGISTERED READING
======================
Fixed before the numbers existed.

    Divergence is material if the Jaccard overlap between the risk ranked and effect
    ranked top decile falls below 0.80. Below that, the two strategies are naming
    substantially different people and the choice between them is a real decision rather
    than a technicality.

    The cost of ranking by risk is the shortfall in expected outcomes averted when the
    risk ranked list is evaluated under an efficacy model that is not proportional. A
    shortfall above 5% is material.

EQUITY IS DISCLOSED BEFORE ANY RECOMMENDATION
=============================================
In the education domain, switching to effect ranking reduced representation of the most
deprived and least formally educated students. Whether the clinical analogue moves the
same way is unknown and is one of the more interesting open questions in the project.
Composition of the selected slice is reported for every available attribute under both
rankings, and it appears above the summary rather than below it.

Usage:
    python 17_mimic_allocation.py

Reads:
    data/processed/mimic_risk_oof.parquet
    data/processed/mimic_features_at_admission.parquet
    data/processed/mimic_features_at_discharge.parquet

Writes:
    docs/17_mimic_allocation.md
    cache/mimic_allocation_stats.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROC = Path("data/processed")
DOCS = Path("docs")
CACHE = Path("cache")

POINTS = ["at_admission", "at_discharge"]
REGIMES = ["A", "B", "C"]
WINDOWS = [30, 90]

CAPACITIES = [0.01, 0.05, 0.10, 0.20]
HEADLINE_CAPACITY = 0.10
HEADLINE_CONFIG = "pooled_recal"
HEADLINE_EFFICACY = "E3"

EFFICACY = {
    "E1": {"kind": "power", "k": 0.20, "alpha": 1.0, "beta": 0.0,
           "label": "proportional"},
    "E2": {"kind": "power", "k": 0.80, "alpha": 1.0, "beta": 1.0,
           "label": "mild attenuation, peak 0.50"},
    "E3": {"kind": "power", "k": 2.37, "alpha": 1.0, "beta": 3.0,
           "label": "strong attenuation, peak 0.25"},
    "E4": {"kind": "ceiling", "k": 0.20, "cap": 0.04,
           "label": "ceiling at 0.04"},
}

JACCARD_MATERIAL = 0.80
SHORTFALL_MATERIAL = 0.05

EQUITY_CANDIDATES = [
    "service_grouped", "race", "insurance", "marital_status",
    "gender", "admission_type", "admission_location", "discharge_location",
]
AGE_CANDIDATES = ["age", "anchor_age", "age_at_admission"]

stats = {}
lines = []


def w(s=""):
    lines.append(s)
    print(s)


def resolve(cols, candidates, what):
    for c in candidates:
        if c in cols:
            return c
    sys.exit(
        f"\nCould not find a column for {what}.\n"
        f"Tried: {candidates}\n"
        f"Available: {sorted(cols)}\n"
        "Paste the schema and the script will be adjusted."
    )


def arr(p, spec):
    if spec["kind"] == "power":
        return spec["k"] * (p ** spec["alpha"]) * ((1.0 - p) ** spec["beta"])
    return np.minimum(spec["cap"], spec["k"] * p)


def top_k(scores, k):
    return np.argsort(-scores, kind="stable")[:k]


def jaccard(a, b):
    a, b = set(a.tolist()), set(b.tolist())
    return len(a & b) / len(a | b) if (a | b) else np.nan


def recalibrate(p, groups, y):
    """Intercept only shift per group so mean predicted matches observed rate."""
    out = p.copy()
    eps = 1e-6
    for g in np.unique(groups):
        m = groups == g
        target = y[m].mean()
        if target <= 0 or target >= 1:
            continue
        lo, hi = -10.0, 10.0
        logit = np.log(np.clip(p[m], eps, 1 - eps) / (1 - np.clip(p[m], eps, 1 - eps)))
        for _ in range(60):
            mid = (lo + hi) / 2
            if (1 / (1 + np.exp(-(logit + mid)))).mean() < target:
                lo = mid
            else:
                hi = mid
        out[m] = 1 / (1 + np.exp(-(logit + (lo + hi) / 2)))
    return out


def composition(idx, frame, cols, age_col):
    out = {}
    sub = frame.iloc[idx]
    for c in cols:
        vc = sub[c].astype(str).value_counts(normalize=True)
        out[c] = {str(k): float(v) for k, v in vc.head(8).items()}
    if age_col:
        out["age_mean"] = float(sub[age_col].mean())
    return out


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

oof_path = PROC / "mimic_risk_oof.parquet"
if not oof_path.exists():
    sys.exit(f"\nMissing {oof_path}. `14_mimic_risk_model.py` writes it.")

oof = pd.read_parquet(oof_path)
cols = set(oof.columns)
print("mimic_risk_oof.parquet columns:", sorted(cols))

COL_POINT = resolve(cols, ["point", "decision_point"], "decision point")
COL_REGIME = resolve(cols, ["regime", "censoring_regime"], "regime")
COL_WINDOW = resolve(cols, ["window", "horizon"], "window")
COL_ID = resolve(cols, ["hadm_id"], "admission id")
COL_Y = resolve(cols, ["readmit", "y", "y_true", "outcome"], "outcome")
COL_P = resolve(
    cols,
    ["risk_logit", "p_logit", "logit_p", "p_logistic", "pred_logit", "p"],
    "logistic predicted probability",
)

_probe = oof[COL_P].to_numpy(dtype=float)
if not (np.nanmin(_probe) >= 0.0 and np.nanmax(_probe) <= 1.0):
    sys.exit(
        f"\n`{COL_P}` ranges {np.nanmin(_probe):.4f} to {np.nanmax(_probe):.4f}, which is "
        "not a probability. The efficacy models and the recalibration both assume a "
        "probability scale. Paste the range and the script will be adjusted."
    )

w("# 17. Allocation under a capacity constraint")
w()
w("Generated by `17_mimic_allocation.py`. Do not edit by hand.")
w()
w(
    "Post processing on the out of fold predictions from `14`. Nothing is fitted here. "
    "Logistic regression throughout, as `15` established."
)
w()
w("## The efficacy models are assumptions")
w()
w(
    "MIMIC contains no randomised intervention. Absolute risk reduction as a function of "
    "baseline risk is supplied, not estimated, and no claim is made about which of these "
    "shapes is true. The deliverable is the map from assumption to allocation."
)
w()
w("| Model | Shape | Note |")
w("|---|---|---|")
for name, spec in EFFICACY.items():
    if spec["kind"] == "power":
        shape = f"ARR = {spec['k']:.2f} p^{spec['alpha']:.0f} (1-p)^{spec['beta']:.0f}"
    else:
        shape = f"ARR = min({spec['cap']:.2f}, {spec['k']:.2f} p)"
    w(f"| {name} | {shape} | {spec['label']} |")
w()
w(
    "E1 is the null case. Under proportional benefit the effect ranking is a monotone "
    "transform of the risk ranking, so the two lists are identical by construction. Any "
    "divergence reported for E1 is a bug in this script, not a finding."
)
w()
w(
    "**E4 is not identified and its Jaccard column must not be read as divergence.** "
    "Benefit saturates at the ceiling for every patient above the threshold risk, so a "
    "large share of the population shares one benefit value and the effect ranking is "
    "choosing arbitrarily among them. The tie sizes are reported below. The shortfall "
    "column for E4 remains meaningful: it says any selection from the tied pool averts "
    "the same total. E4 is retained for that reason and for no other."
)
w()
w("## Pre registered reading")
w()
w("| Quantity | Material if |")
w("|---|---|")
w(f"| Jaccard, risk ranked against effect ranked top decile | below {JACCARD_MATERIAL:.2f} |")
w(f"| Shortfall in expected outcomes averted from ranking by risk | above {SHORTFALL_MATERIAL:.0%} |")
w()

results = {}
equity = {}
t0 = time.time()

for point in POINTS:
    feats = pd.read_parquet(PROC / f"mimic_features_{point}.parquet")
    eq_cols = [c for c in EQUITY_CANDIDATES if c in feats.columns]
    age_col = next((c for c in AGE_CANDIDATES if c in feats.columns), None)
    svc_col = "service_grouped"
    if svc_col not in feats.columns:
        sys.exit(f"\nMissing {svc_col} in features. Available: {sorted(feats.columns)}")

    for regime in REGIMES:
        for wd in WINDOWS:
            o = oof[
                (oof[COL_POINT] == point)
                & (oof[COL_REGIME] == regime)
                & (oof[COL_WINDOW] == wd)
            ]
            f = feats[(feats["regime"] == regime) & (feats["window"] == wd)]
            if len(o) == 0:
                sys.exit(f"\nNo rows in oof for {point} {regime} {wd}.")

            m = o[[COL_ID, COL_Y, COL_P]].merge(
                f[[c for c in set([COL_ID, svc_col] + eq_cols + ([age_col] if age_col else []))]],
                on=COL_ID, how="inner",
            ).reset_index(drop=True)
            assert len(m) == len(o), (
                f"merge lost rows for {point} {regime} {wd}: {len(o)} to {len(m)}"
            )

            y = m[COL_Y].to_numpy()
            p_raw = m[COL_P].to_numpy(dtype=float)
            svc = m[svc_col].astype(str).to_numpy()
            n = len(m)

            configs = {
                "pooled_raw": p_raw,
                "pooled_recal": recalibrate(p_raw, svc, y),
            }

            cell_key = f"{point}_{regime}_{wd}"
            cell = {"point": point, "regime": regime, "window": wd, "n": int(n),
                    "base_rate": float(y.mean()), "configs": {}}

            for cfg_name, p in configs.items():
                cfg = {"capacities": {}}
                for cap in CAPACITIES:
                    k = max(1, int(round(cap * n)))
                    risk_idx = top_k(p, k)
                    entry = {"k": int(k), "efficacy": {}}
                    for e_name, spec in EFFICACY.items():
                        benefit = arr(p, spec)
                        eff_idx = top_k(benefit, k)
                        r12 = np.round(benefit, 12)
                        cut_val = r12[eff_idx].min()
                        entry["efficacy"][e_name] = {
                            "jaccard": float(jaccard(risk_idx, eff_idx)),
                            "averted_risk_rank": float(benefit[risk_idx].sum()),
                            "averted_effect_rank": float(benefit[eff_idx].sum()),
                            "shortfall": float(
                                1 - benefit[risk_idx].sum() / benefit[eff_idx].sum()
                            ) if benefit[eff_idx].sum() > 0 else np.nan,
                            "events_risk_rank": int(y[risk_idx].sum()),
                            "events_effect_rank": int(y[eff_idx].sum()),
                            "max_tie_selected": int(
                                np.unique(r12[eff_idx], return_counts=True)[1].max()
                            ),
                            "tied_at_cut_population": int((r12 == cut_val).sum()),
                        }
                    cfg["capacities"][f"{cap:.2f}"] = entry
                cell["configs"][cfg_name] = cfg

            # within service: capacity split proportional to service size
            cfg = {"capacities": {}}
            for cap in CAPACITIES:
                risk_sel, eff_sel = [], {e: [] for e in EFFICACY}
                for g in np.unique(svc):
                    gi = np.flatnonzero(svc == g)
                    kg = max(1, int(round(cap * len(gi))))
                    pg = p_raw[gi]
                    risk_sel.append(gi[top_k(pg, kg)])
                    for e_name, spec in EFFICACY.items():
                        eff_sel[e_name].append(gi[top_k(arr(pg, spec), kg)])
                risk_idx = np.concatenate(risk_sel)
                entry = {"k": int(len(risk_idx)), "efficacy": {}}
                for e_name, spec in EFFICACY.items():
                    eidx = np.concatenate(eff_sel[e_name])
                    benefit = arr(p_raw, spec)
                    entry["efficacy"][e_name] = {
                        "jaccard": float(jaccard(risk_idx, eidx)),
                        "averted_risk_rank": float(benefit[risk_idx].sum()),
                        "averted_effect_rank": float(benefit[eidx].sum()),
                        "shortfall": float(
                            1 - benefit[risk_idx].sum() / benefit[eidx].sum()
                        ) if benefit[eidx].sum() > 0 else np.nan,
                        "events_risk_rank": int(y[risk_idx].sum()),
                        "events_effect_rank": int(y[eidx].sum()),
                    }
                cfg["capacities"][f"{cap:.2f}"] = entry
            cell["configs"]["within_service"] = cfg

            # equity at the headline configuration and efficacy
            k = max(1, int(round(HEADLINE_CAPACITY * n)))
            p_head = configs[HEADLINE_CONFIG]
            r_idx = top_k(p_head, k)
            e_idx = top_k(arr(p_head, EFFICACY[HEADLINE_EFFICACY]), k)
            equity[cell_key] = {
                "population": composition(np.arange(n), m, eq_cols, age_col),
                "risk_ranked": composition(r_idx, m, eq_cols, age_col),
                "effect_ranked": composition(e_idx, m, eq_cols, age_col),
                "displaced": int(k - len(set(r_idx.tolist()) & set(e_idx.tolist()))),
            }

            results[cell_key] = cell
            print(f"  done {cell_key}  ({time.time() - t0:.0f}s elapsed)")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

cap_key = f"{HEADLINE_CAPACITY:.2f}"

w("## Sanity check on the null case")
w()
w(
    "E1 must show Jaccard 1.000 everywhere. If it does not, the divergence reported below "
    "is an artifact."
)
w()
bad = [
    k for k, r in results.items()
    for cfg in r["configs"].values()
    if abs(cfg["capacities"][cap_key]["efficacy"]["E1"]["jaccard"] - 1.0) > 1e-9
]
w(f"Cells where E1 diverges: **{len(bad)}**" + (f" ({', '.join(bad[:5])})" if bad else ""))
w()

w("## Identification check")
w()
w(
    "An efficacy model is identified only if the effect ranking it implies is unique. "
    "Where many patients share one benefit value, the selection among them is decided by "
    "row order rather than by benefit, and the resulting overlap statistic measures the "
    "sort implementation."
)
w()
w(f"Largest tied group inside the selected slice, `{HEADLINE_CONFIG}`, "
  f"{HEADLINE_CAPACITY:.0%} capacity.")
w()
w("| Point | Regime | Window | k | E1 | E2 | E3 | E4 | E4 tied in population |")
w("|---|---|---:|---:|---:|---:|---:|---:|---:|")
for r in results.values():
    c = r["configs"][HEADLINE_CONFIG]["capacities"][cap_key]
    ties = " | ".join(f"{c['efficacy'][n]['max_tie_selected']:,}" for n in EFFICACY)
    w(
        f"| {r['point']} | {r['regime']} | {r['window']} | {c['k']:,} | {ties} | "
        f"{c['efficacy']['E4']['tied_at_cut_population']:,} |"
    )
w()
w(
    "A tied group approaching k means the effect ranking under that model is arbitrary. "
    "Read the E4 Jaccard column in the next section in that light, and read E1, E2 and E3 "
    "as identified only where their tie counts are small."
)
w()

w(f"## Divergence at the {HEADLINE_CAPACITY:.0%} capacity, `{HEADLINE_CONFIG}`")
w()
w("Jaccard overlap between the risk ranked list and the effect ranked list.")
w()
w("| Point | Regime | Window | E1 | E2 | E3 | E4 |")
w("|---|---|---:|---:|---:|---:|---:|")
for r in results.values():
    e = r["configs"][HEADLINE_CONFIG]["capacities"][cap_key]["efficacy"]
    vals = " | ".join(f"{e[n]['jaccard']:.3f}" for n in EFFICACY)
    w(f"| {r['point']} | {r['regime']} | {r['window']} | {vals} |")
w()

w("## The cost of ranking by risk")
w()
w(
    "Expected outcomes averted under the risk ranked list, as a shortfall against the "
    "effect ranked list evaluated under the same efficacy model. Zero by construction "
    "under E1."
)
w()
w("| Point | Regime | Window | E2 | E3 | E4 |")
w("|---|---|---:|---:|---:|---:|")
for r in results.values():
    e = r["configs"][HEADLINE_CONFIG]["capacities"][cap_key]["efficacy"]
    vals = " | ".join(f"{e[n]['shortfall']:.1%}" for n in ["E2", "E3", "E4"])
    w(f"| {r['point']} | {r['regime']} | {r['window']} | {vals} |")
w()

w(f"## Configuration comparison, {HEADLINE_EFFICACY}, {HEADLINE_CAPACITY:.0%} capacity")
w()
w(
    "`pooled_raw` and `pooled_recal` differ only in a per service intercept shift, which "
    "cannot reorder patients within a service. Any difference between them is a re "
    "weighting between services."
)
w()
w("| Point | Regime | Window | Config | Jaccard | Shortfall | Events, risk rank | Events, effect rank |")
w("|---|---|---:|---|---:|---:|---:|---:|")
for r in results.values():
    for cfg_name, cfg in r["configs"].items():
        e = cfg["capacities"][cap_key]["efficacy"][HEADLINE_EFFICACY]
        w(
            f"| {r['point']} | {r['regime']} | {r['window']} | {cfg_name} | "
            f"{e['jaccard']:.3f} | {e['shortfall']:.1%} | "
            f"{e['events_risk_rank']:,} | {e['events_effect_rank']:,} |"
        )
w()

w(f"## Divergence across capacity, `{HEADLINE_CONFIG}`, {HEADLINE_EFFICACY}")
w()
w("| Point | Regime | Window | 1% | 5% | 10% | 20% |")
w("|---|---|---:|---:|---:|---:|---:|")
for r in results.values():
    vals = " | ".join(
        f"{r['configs'][HEADLINE_CONFIG]['capacities'][f'{c:.2f}']['efficacy'][HEADLINE_EFFICACY]['jaccard']:.3f}"
        for c in CAPACITIES
    )
    w(f"| {r['point']} | {r['regime']} | {r['window']} | {vals} |")
w()

w("## Who the two lists select")
w()
w(
    "Composition of the selected slice under each ranking, against the population it was "
    "drawn from. This appears before the summary deliberately. In the education domain, "
    "effect ranking reduced representation of the most deprived students, and a "
    "recommendation that does not disclose the analogous movement here is not a "
    "recommendation a programme can act on."
)
w()

ref_key = f"at_discharge_A_30"
if ref_key in equity:
    eq = equity[ref_key]
    w(f"Reference cell `{ref_key}`, `{HEADLINE_CONFIG}`, {HEADLINE_EFFICACY}, "
      f"{HEADLINE_CAPACITY:.0%} capacity. Displaced by the switch: **{eq['displaced']:,}**.")
    w()
    for attr in eq["population"]:
        if attr == "age_mean":
            continue
        w(f"**{attr}**")
        w()
        w("| Level | Population | Risk ranked | Effect ranked | Shift |")
        w("|---|---:|---:|---:|---:|")
        for lvl, pop in sorted(eq["population"][attr].items(), key=lambda x: -x[1]):
            rr = eq["risk_ranked"][attr].get(lvl, 0.0)
            er = eq["effect_ranked"][attr].get(lvl, 0.0)
            w(f"| {lvl} | {pop:.1%} | {rr:.1%} | {er:.1%} | {er - rr:+.1%} |")
        w()
    if "age_mean" in eq["population"]:
        w(
            f"Mean age: population {eq['population']['age_mean']:.1f}, "
            f"risk ranked {eq['risk_ranked']['age_mean']:.1f}, "
            f"effect ranked {eq['effect_ranked']['age_mean']:.1f}."
        )
        w()

jac = np.array([
    r["configs"][HEADLINE_CONFIG]["capacities"][cap_key]["efficacy"][HEADLINE_EFFICACY]["jaccard"]
    for r in results.values()
])
sf = np.array([
    r["configs"][HEADLINE_CONFIG]["capacities"][cap_key]["efficacy"][HEADLINE_EFFICACY]["shortfall"]
    for r in results.values()
])

w("## Summary")
w()
w("| Quantity | Value |")
w("|---|---:|")
w(f"| Cells | {len(results)} |")
w(f"| Divergence material ({HEADLINE_EFFICACY}) | {int((jac < JACCARD_MATERIAL).sum())} of {len(results)} |")
w(f"| Shortfall material ({HEADLINE_EFFICACY}) | {int((sf > SHORTFALL_MATERIAL).sum())} of {len(results)} |")
w(f"| Mean Jaccard | {jac.mean():.3f} |")
w(f"| Mean shortfall | {sf.mean():.1%} |")
w()
w(
    "Every number in this section is conditional on an efficacy shape that was assumed "
    "rather than measured. Under E1 there is no divergence at all and risk ranking is "
    "correct. The finding is not that effect ranking wins. It is that the answer depends "
    "entirely on a quantity no one in this data has estimated, and that the conventional "
    "approach assumes one particular answer to it without saying so."
)
w()

stats["results"] = results
stats["equity"] = equity
stats["efficacy"] = EFFICACY
stats["thresholds"] = {
    "jaccard_material": JACCARD_MATERIAL,
    "shortfall_material": SHORTFALL_MATERIAL,
}
stats["runtime_seconds"] = round(time.time() - t0, 1)

(DOCS / "17_mimic_allocation.md").write_text("\n".join(lines), encoding="utf-8")
(CACHE / "mimic_allocation_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

print()
print(f"Total runtime: {time.time() - t0:.0f}s")
print("Wrote docs/17_mimic_allocation.md")
print("Wrote cache/mimic_allocation_stats.json")
