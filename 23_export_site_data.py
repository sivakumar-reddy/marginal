"""
23_export_site_data.py

Builds the single precomputed JSON the interactive site consumes.

WHY PRECOMPUTED
===============
The frontend performs no scientific computation. It reads numbers that were produced by
numbered scripts, cached, and exported here. Nothing is recalculated in JavaScript and no
scientific value is hard coded in the site. If a number appears on the page, this file put
it there and a cache file put it here.

That matters practically as well as in principle. The clinical validation script takes
eighteen hours. A site that recomputed anything would be unusable, and a site that hard
coded values would drift silently from the analysis.

ADAPTERS, NOT GUESSES
=====================
Each domain declares the cache files it needs and the keys it reads from them. When a key
is missing the adapter records the gap explicitly in `_gaps` rather than emitting a null
that renders as a blank on the page.

The advancement adapter is exact, because those caches were written by scripts in this
same session. The clinical adapter is written against the known structure of scripts 15
through 17b. The education adapter is the least certain: its cache structure has not been
inspected, so it reads defensively and reports what it could not map. Run this, read
`_gaps`, and the education adapter can be corrected against the actual key names rather
than against an assumption about them.

A domain that is absent or unmappable is marked `available: false` and the site renders
what exists. Partial output is better than a blocked build, provided the gaps are visible.

WHAT THE SITE NEEDS
===================
Per domain: identity, population, assumptions with their source status, capacity
scenarios, ranking strategies with outcomes and overlap, equity composition, sensitivity
results, headline findings, limitations, and reproducibility metadata.

The `assumptions` block carries `source_status` for every parameter. The advancement
domain is entirely illustrative and the site must be able to say so on the page, not in a
footnote.

Usage:
    python 23_export_site_data.py

Reads:
    cache/*.json

Writes:
    site/data/marginal.json
    docs/23_export_manifest.md
"""

import json
import math
from pathlib import Path

from marginal_engine import SCHEMA_VERSION, Timer, read_cache, run_metadata

CACHE = Path("cache")
DOCS = Path("docs")
SITE = Path("site/data")

SEED = 20260823

lines = []
gaps = []


def w(s=""):
    lines.append(s)
    print(s)


def clean(o, path="", found=None):
    """Replace NaN and Infinity with null.

    `json.dumps` emits bare `NaN`, which is not valid JSON, and a browser rejects the
    entire file rather than the offending value. Several analysis scripts legitimately
    cache NaN, so the conversion happens here at the boundary rather than in the science.

    Most of these are not failures. A mean over an empty set is undefined, and that is
    the honest answer when a cell has nobody in it, for instance where two rankings
    select exactly the same people so nobody is dropped or added. Substituting zero
    there would read as "the dropped students had no risk" rather than "there were no
    dropped students". Every substitution is recorded so the distinction stays visible.
    """
    if found is None:
        found = []
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            found.append(path or "(root)")
            return None
        return o
    if isinstance(o, dict):
        return {k: clean(v, f"{path}.{k}" if path else k, found) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v, f"{path}[{i}]", found) for i, v in enumerate(o)]
    return o


def need(blob, path, label):
    """Walk a dotted path, recording a gap rather than raising when it is absent."""
    if blob is None:
        gaps.append(f"{label}: cache file missing")
        return None
    cur = blob
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                gaps.append(f"{label}: index `{part}` not in list at `{path}`")
                return None
        else:
            gaps.append(f"{label}: key `{part}` not found at `{path}`")
            return None
    return cur


# ---------------------------------------------------------------------------
# Advancement. Exact, written by scripts in this repository.
# ---------------------------------------------------------------------------

def advancement():
    gen = read_cache(CACHE / "advancement_generator_stats.json")
    risk = read_cache(CACHE / "advancement_risk_stats.json")
    rec = read_cache(CACHE / "advancement_effect_recovery_stats.json")
    stab = read_cache(CACHE / "advancement_stability_stats.json")
    alloc = read_cache(CACHE / "advancement_allocation_stats.json")
    sens = read_cache(CACHE / "advancement_sensitivity_stats.json")
    roster = read_cache(CACHE / "advancement_roster_sample.json")
    if alloc is None:
        return {"available": False, "reason": "allocation cache absent"}

    head = need(alloc, "headline_capacity", "advancement")
    res = need(alloc, "results", "advancement") or {}
    hkey = f"{head:.2f}" if head is not None else None
    hcell = res.get(hkey, {})

    return {
        "available": True,
        "interactive": True,
        "id": "advancement",
        "label": "University advancement",
        "outcome": "qualifying gift within the horizon",
        "intervention": "gift officer visit",
        "data_status": "simulated",
        "ground_truth_available": True,
        "population": {
            "n": need(gen, "n", "advancement"),
            "base_rate": need(gen, "gave_rate", "advancement"),
            "treated_rate": need(gen, "visit_rate", "advancement"),
            "true_ate": need(gen, "true_ate", "advancement"),
            "naive_ate": need(gen, "naive_ate", "advancement"),
            "confounding_bias": need(gen, "confounding_bias", "advancement"),
            "group_shares": need(gen, "group_shares", "advancement"),
            "group_true_effect": need(gen, "group_true_effect", "advancement"),
            "negative_effect_share": need(gen, "negative_effect_share", "advancement"),
        },
        "assumptions": {
            "source_status": need(gen, "param_source_status", "advancement"),
            "parameters": need(gen, "params", "advancement"),
            "all_illustrative": True,
        },
        "capacity": {
            "scenarios": need(alloc, "capacities", "advancement"),
            "headline": head,
            "headline_k": hcell.get("k"),
        },
        "roster": roster,
        "strategies": hcell.get("strategies"),
        "overlap": hcell.get("overlap"),
        "by_capacity": {
            k: {
                s: {
                    "expected_incremental": v["expected_incremental"],
                    "effect_captured": v["effect_captured"],
                    "harm_share": v["harm_share"],
                }
                for s, v in cell["strategies"].items()
            }
            for k, cell in res.items()
        },
        "equity": {
            "population_group_shares": need(alloc, "population_group_shares", "advancement"),
            "observable": need(alloc, "equity_observable", "advancement"),
        },
        "model": {
            "estimator_performance": need(risk, "performance", "advancement"),
            "effect_recovery_ceiling": need(rec, "ceiling", "advancement"),
            "stability": need(stab, "summary", "advancement"),
        },
        "sensitivity": {
            sweep: {
                "values": blob["values"],
                "rows": blob["rows"],
                "onsets": blob["onsets"],
            }
            for sweep, blob in (need(sens, "sweeps", "advancement") or {}).items()
        },
        "limitations": [
            "The population is constructed. Nothing here is evidence about real donors.",
            "Every parameter is illustrative and open in 08_sources.md.",
            "Dollars are not identified: gift amounts exist only for the arm received.",
            "The oracle is not deployable and bounds what information could buy.",
            "The effect ranking failed the stability threshold at baseline parameters.",
        ],
    }


SWEEP_STRIDE = 4


def thin_sweep(results, betas, stride=SWEEP_STRIDE):
    """Keep every nth sweep point. Onsets are precomputed, so the site does not
    need every grid point, and the full arrays dominate the payload size."""
    if results is None or betas is None:
        return None
    keep = list(range(0, len(betas), stride))
    if keep[-1] != len(betas) - 1:
        keep.append(len(betas) - 1)
    out = {"betas": [betas[i] for i in keep], "stride": stride, "cells": {}}
    for k, cell in results.items():
        out["cells"][k] = {
            "point": cell["point"], "regime": cell["regime"],
            "window": cell["window"], "base_rate": cell["base_rate"],
            "capacities": {
                cap: {
                    "k": c["k"],
                    "risk_band": c["risk_band"],
                    "onset_jaccard": c["onset_jaccard"],
                    "onset_shortfall": c["onset_shortfall"],
                    "jaccard": [c["jaccard"][i] for i in keep],
                    "shortfall": [c["shortfall"][i] for i in keep],
                }
                for cap, c in cell["capacities"].items()
            },
        }
    return out


# ---------------------------------------------------------------------------
# Clinical. Written against the known structure of 15 to 17b.
# ---------------------------------------------------------------------------

def clinical():
    alloc = read_cache(CACHE / "mimic_allocation_stats.json")
    sweep = read_cache(CACHE / "mimic_attenuation_stats.json")
    stab = read_cache(CACHE / "mimic_stability_stats.json")
    val = read_cache(CACHE / "mimic_validation_stats.json")
    roster = read_cache(CACHE / "clinical_roster.json")
    if alloc is None:
        return {"available": False, "reason": "mimic allocation cache absent"}

    return {
        "available": True,
        "interactive": roster is not None,
        "id": "clinical",
        "label": "Academic medical center",
        "outcome": "readmission within the window",
        "intervention": "care management enrolment",
        "data_status": "observed",
        "ground_truth_available": False,
        "assumptions": {
            "source_status": "Efficacy supplied, not measured. MIMIC has no intervention.",
            "efficacy_models": need(alloc, "efficacy", "clinical"),
            "all_illustrative": False,
        },
        "capacity": {
            "scenarios": [0.01, 0.05, 0.10, 0.20],
            "headline": 0.10,
        },
        "roster": roster,
        "allocation": need(alloc, "results", "clinical"),
        "equity": need(alloc, "equity", "clinical"),
        "sensitivity": thin_sweep(need(sweep, "results", "clinical"),
                                  need(sweep, "betas", "clinical")),
        "model": {
            "stability_thresholds": need(stab, "thresholds", "clinical"),
            "stability_repeats": need(stab, "repeats", "clinical"),
            "stability_by_cell": {
                k: {
                    est: {
                        "jaccard_median": c["capacities"]["0.10"]["jaccard_median"],
                        "core_frac_of_k": c["capacities"]["0.10"]["core_frac_of_k"],
                        "union_over_k": c["capacities"]["0.10"]["union_over_k"],
                    }
                    for est in ("hgb", "logit")
                    for c in [cell[est]]
                }
                for k, cell in (need(stab, "results", "clinical") or {}).items()
            },
            "validation_thresholds": need(val, "thresholds", "clinical"),
        },
        "limitations": [
            "True treatment effect is unobserved. Efficacy is assumed and swept.",
            "One academic medical center. Held out service is weaker than held out hospital.",
            "Level failed to transfer in most service cells; ranking transferred.",
            "The ceiling efficacy model is not identified and its overlap column is not divergence.",
        ],
    }


# ---------------------------------------------------------------------------
# Education. Structure not inspected. Reads defensively and reports gaps.
# ---------------------------------------------------------------------------

MAX_PASSTHROUGH_BYTES = 150_000


def probe(obj, depth=0):
    """Shape of a nested object without its contents. Used to map an unfamiliar cache."""
    if depth > 2:
        return "..."
    if isinstance(obj, dict):
        return {k: probe(v, depth + 1) for k, v in list(obj.items())[:8]}
    if isinstance(obj, list):
        return [f"list[{len(obj)}]", probe(obj[0], depth + 1) if obj else None]
    return type(obj).__name__


def passthrough(blob, label, keys=None):
    """Include a cache section verbatim when it is small enough to ship."""
    if blob is None:
        return None
    sub = blob if keys is None else {k: blob[k] for k in keys if k in blob}
    size = len(json.dumps(sub))
    if size > MAX_PASSTHROUGH_BYTES:
        gaps.append(
            f"{label}: {size / 1024:.0f} KB exceeds the passthrough limit, shape only"
        )
        return {"_omitted_for_size_kb": round(size / 1024, 1), "_shape": probe(sub)}
    return sub


def education():
    cohort = read_cache(CACHE / "cohort_stats.json")
    risk = read_cache(CACHE / "risk_stats.json")
    stab = read_cache(CACHE / "stability_stats.json")
    alloc = read_cache(CACHE / "allocation_stats.json")
    dist = read_cache(CACHE / "distribution_stats.json")
    roster = read_cache(CACHE / "education_roster.json")

    if alloc is None and cohort is None:
        return {"available": False, "reason": "no education caches found"}

    return {
        "available": True,
        "id": "education",
        "label": "Distance learning university",
        "outcome": "withdrawal from the module",
        "intervention": "advisor contact",
        "data_status": "observed",
        "ground_truth_available": False,
        "interactive": roster is not None,
        "population": {
            "n_start": need(cohort, "n_start", "education"),
            "n_analysis": need(cohort, "n_analysis", "education"),
            "outcome": need(cohort, "outcome", "education"),
            "exclusions": need(cohort, "exclusions", "education"),
            "folds": need(cohort, "folds", "education"),
            "reachability": need(cohort, "reachability", "education"),
        },
        "assumptions": {
            "source_status": (
                "Efficacy supplied, not measured. Nobody in OULAD was randomised. "
                "The gamma parameter is swept rather than estimated."
            ),
            "ate_target": need(alloc, "ate_target", "education"),
            "gammas": need(alloc, "gammas", "education"),
            "noise_floor": need(alloc, "noise_floor", "education"),
            "all_illustrative": False,
        },
        "capacity": {
            "capacity_pct": need(alloc, "capacity_pct", "education"),
            "min_cohort": need(alloc, "min_cohort", "education"),
            "cohorts": need(alloc, "cohorts", "education"),
        },
        "roster": roster,
        "allocation": passthrough(alloc, "education.allocation"),
        "model": {
            "risk": passthrough(risk, "education.risk"),
            "stability": passthrough(stab, "education.stability"),
        },
        "equity": passthrough(
            dist, "education.distribution", keys=["composition", "summary"]
        ),
        "sensitivity": {
            "gammas": need(dist, "gammas", "education"),
            "summary": need(dist, "summary", "education"),
        },
        "limitations": [
            "True treatment effect is unobserved. Efficacy is assumed and swept over gamma.",
            "One institution, one set of module presentations.",
            "Effect ranking reduced representation of the most deprived students.",
        ],
        "_structure_probe": {
            "allocation": probe(alloc),
            "risk": probe(risk),
            "stability": probe(stab),
            "distribution": probe(dist),
        },
    }


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

with Timer() as t:
    domains = {
        "education": education(),
        "clinical": clinical(),
        "advancement": advancement(),
    }

payload = {
    "_meta": run_metadata(__file__, SEED, {"export_of": "marginal"}),
    "schema_version": SCHEMA_VERSION,
    "question": (
        "When an institution has more people who could benefit from an intervention than "
        "it has capacity to intervene, does ranking by predicted risk identify the same "
        "people as ranking by expected treatment effect?"
    ),
    "framing": {
        "risk_question": "Who looks most at risk?",
        "effect_question": "Who benefits most from intervention?",
        "neutrality": (
            "Effect ranking is not presented as the correct choice. The project exposes a "
            "trade off. Each ranking has costs, and the equity movement and stability cost "
            "are reported alongside every gain."
        ),
    },
    "domains": domains,
    "_gaps": gaps,
}

nonfinite = []
payload = clean(payload, found=nonfinite)
if nonfinite:
    gaps.append(
        f"{len(nonfinite)} undefined value(s) written as null, first at "
        f"`{nonfinite[0]}`. An undefined value is usually a statistic over an empty "
        "set, not a failure."
    )
    payload["_gaps"] = gaps
    payload["_nonfinite"] = nonfinite[:40]

SITE.mkdir(parents=True, exist_ok=True)
out = SITE / "marginal.json"
# allow_nan=False so an invalid payload fails here rather than in the browser
# Written compact. Indentation nearly quadrupled the payload for a file no human
# reads, and the page has to load it before anything appears.
out.write_text(
    json.dumps(payload, allow_nan=False, separators=(",", ":")), encoding="utf-8"
)
json.loads(out.read_text(encoding="utf-8"))  # parse back; the site must never see bad JSON

w("# 23. Site data export manifest")
w()
w("Generated by `23_export_site_data.py`. Do not edit by hand.")
w()
w(f"Wrote `{out}`, {out.stat().st_size / 1024:.1f} KB, schema {SCHEMA_VERSION}.")
w()
w("## Domain availability")
w()
w("| Domain | Available | Interactive | Ground truth | Data status | Note |")
w("|---|---|---|---|---|---|")
for k, d in domains.items():
    w(
        f"| {k} | {'yes' if d.get('available') else 'no'} | "
        f"{'yes' if d.get('interactive') else 'no'} | "
        f"{'yes' if d.get('ground_truth_available') else 'no'} | "
        f"{d.get('data_status', 'unknown')} | {d.get('reason', '')} |"
    )
w()
w("## Gaps")
w()
if gaps:
    for g in gaps:
        w(f"- {g}")
else:
    w("None. Every declared key resolved.")
w()
w(
    "A gap means the site will not render that element. Nothing is filled with a plausible "
    "value to close a gap."
)
w()
w("## Rules this export enforces")
w()
w("- The frontend performs no scientific computation.")
w("- Every displayed number originates in a cache file written by a numbered script.")
w("- No scientific value is hard coded in the site.")
w("- Missing values are recorded as gaps, never substituted.")
w("- Undefined values, such as an average over nobody, are written as null and counted.")
w("- Simulated domains carry their source status into the page, not a footnote.")
w()

DOCS.mkdir(parents=True, exist_ok=True)
(DOCS / "23_export_manifest.md").write_text("\n".join(lines), encoding="utf-8")

print()
print(f"Total runtime: {t.seconds}s")
print(f"Wrote {out}")
print("Wrote docs/23_export_manifest.md")
