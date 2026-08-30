"""
marginal_engine.py

Shared primitives for the Marginal project.

SCOPE, DELIBERATELY NARROW
==========================
This module exists because scripts 19 through 22 and the export step reimplemented the
same handful of operations. It does not exist to abstract the domains.

Education scripts 01 to 10 and clinical scripts 11 to 17b are complete and reproducible.
They are NOT refactored to use this module. Rewriting working, verified analysis to route
through a new abstraction would risk silently changing published results for no analytical
gain, and the project's own standard is that every figure traces to the script that
produced it. Those scripts keep their own copies of these functions.

New code uses this module. Old code is left alone. The duplication is intentional and is
cheaper than the risk.

WHAT BELONGS HERE
=================
Operations that are genuinely identical across domains and carry no domain meaning:
selection under capacity, set overlap, calibration error, threshold crossing, composition
summaries, cache serialisation, reproducibility metadata.

WHAT DOES NOT BELONG HERE
=========================
Efficacy models, censoring regimes, uplift group structure, decision points, service
definitions. Those are domain mechanisms. Forcing them into a common interface would make
the three domains look more alike than they are, and the differences between them are the
project's contribution.

TIE HANDLING
============
Every selection uses a stable sort, so ties break by row order deterministically. That is
reproducible but arbitrary, and `17` showed it can silently manufacture a result when an
efficacy model saturates. `max_tie` reports the largest tied group inside a selection so
that non identification is visible rather than assumed away.
"""

import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np

SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Selection under capacity
# ---------------------------------------------------------------------------

def capacity_k(n, capacity):
    """Number selected at a fractional capacity. At least one."""
    return max(1, int(round(capacity * n)))


def top_k(scores, k):
    """Indices of the k highest scores. Stable sort, so ties break by row order."""
    return np.argsort(-np.asarray(scores), kind="stable")[:k]


def max_tie(scores, idx, decimals=12):
    """Largest tied group inside a selection. Large values mean the ranking is arbitrary."""
    v = np.round(np.asarray(scores)[idx], decimals)
    return int(np.unique(v, return_counts=True)[1].max()) if len(v) else 0


def jaccard(a, b):
    a, b = set(np.asarray(a).tolist()), set(np.asarray(b).tolist())
    return len(a & b) / len(a | b) if (a | b) else float("nan")


def pairwise_jaccard(sets):
    """Median, min and the full list of pairwise overlaps across repeats."""
    vals = [jaccard(a, b) for a, b in combinations(sets, 2)]
    if not vals:
        return {"median": float("nan"), "min": float("nan"), "values": []}
    return {
        "median": float(np.median(vals)),
        "min": float(np.min(vals)),
        "values": [float(v) for v in vals],
    }


def churn(sets, k):
    """Core is the share present in every repeat. Union over k is total distinct named."""
    ss = [set(np.asarray(s).tolist()) for s in sets]
    core = set.intersection(*ss) if ss else set()
    union = set().union(*ss) if ss else set()
    return {"core_frac_of_k": len(core) / k, "union_over_k": len(union) / k}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def ece(y, p, n_bins=10):
    """Expected calibration error over equal count bins."""
    y, p = np.asarray(y), np.asarray(p)
    order = np.argsort(p)
    y, p = y[order], p[order]
    err, total = 0.0, 0
    for b in np.array_split(np.arange(len(y)), n_bins):
        if len(b) == 0:
            continue
        err += len(b) * abs(p[b].mean() - y[b].mean())
        total += len(b)
    return err / total if total else float("nan")


def capture(y, scores, capacity):
    """Share of all events landing in the selected slice."""
    y = np.asarray(y)
    k = capacity_k(len(y), capacity)
    sel = top_k(scores, k)
    return float(y[sel].sum() / y.sum()) if y.sum() else float("nan")


def lift(y, scores, capacity):
    """Capture expressed against random selection. 1.0 is no better than chance."""
    c = capture(y, scores, capacity)
    return c / capacity if capacity else float("nan")


def onset(xs, ys, threshold, below=True):
    """First x where the series crosses the threshold, linearly interpolated."""
    xs, v = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    hit = v < threshold if below else v > threshold
    if not hit.any():
        return None
    i = int(np.argmax(hit))
    if i == 0:
        return float(xs[0])
    y0, y1 = v[i - 1], v[i]
    if y1 == y0:
        return float(xs[i])
    return float(xs[i - 1] + (threshold - y0) * (xs[i] - xs[i - 1]) / (y1 - y0))


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def composition(values, idx, max_levels=12):
    """Selected share by level, with representation relative to the population."""
    values = np.asarray(values).astype(str)
    levels = sorted(set(values.tolist()))
    if len(levels) > max_levels:
        return None
    sel = values[np.asarray(idx)]
    out = {}
    for lv in levels:
        pop = float((values == lv).mean())
        got = float((sel == lv).mean())
        out[lv] = {
            "population": pop,
            "selected": got,
            "representation": (got / pop) if pop > 0 else None,
        }
    return out


# ---------------------------------------------------------------------------
# Reproducibility metadata
# ---------------------------------------------------------------------------

def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return None


def file_digest(path, length=16):
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()[:length]


def run_metadata(script, seed, extra=None):
    """Everything needed to reproduce a run, attached to every cache file."""
    meta = {
        "schema_version": SCHEMA_VERSION,
        "script": str(script),
        "script_digest": file_digest(script),
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
    }
    if extra:
        meta.update(extra)
    return meta


def write_cache(path, payload, script, seed, extra=None):
    """Write a cache file wrapped in a reproducibility envelope."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"_meta": run_metadata(script, seed, extra), **payload}
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return path


def read_cache(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


class Timer:
    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *a):
        self.seconds = round(time.time() - self.t0, 1)
