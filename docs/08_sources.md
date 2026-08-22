# 08. Sources

Every dataset, benchmark and published figure the project depends on. Nothing may be
cited anywhere in this repository unless it appears here with a source and a date.

Items marked OPEN are unverified. Claims resting on them are not defensible until closed.

---

## Datasets

### OULAD, Open University Learning Analytics Dataset

| Field | Value |
|---|---|
| Landing page | https://research.stem.open.ac.uk/ouanalyse/dataset/ |
| File retrieved | http://schools.stem.open.ac.uk/cdn/files/anonymisedData.zip |
| Retrieved | 2026-08-22 |
| Size | 44.6 MB |
| SHA256 | 90DDA45037939953F979072FA70A809EBE07E90EC783C408762AF7698A3825EC |
| Licence | OPEN. Record the exact terms from the landing page. |
| Required citation | OPEN. The landing page specifies a citation; record it verbatim. |

Notes. The download link is plain HTTP with no version string, so the file could change
without notice. The hash above identifies the exact copy every figure in this repository
was computed from. The Open University also operates OU Analyse, a deployed weekly
updating risk of failure system for the same institution, which is the practice this
project examines.

### MIMIC-IV

| Field | Value |
|---|---|
| Source | PhysioNet |
| Credentialed access | Held |
| Data use agreement for required tables | OPEN. Confirm the signed agreement covers full MIMIC-IV rather than MIMIC-IV-ED only. |
| Version | OPEN |
| Retrieved | OPEN |
| Required citation | OPEN |

### Advancement domain population

Constructed, not observed. No public individual level donor portfolio dataset is known
to exist, which is itself an OPEN claim requiring verification. Every parameter of the
constructed population must be traceable to a published benchmark recorded below.

| Parameter | Source | Status |
|---|---|---|
| Giving distribution | | OPEN |
| Donor retention rate | | OPEN |
| Gift officer portfolio size | | OPEN |

---

## Published effect sizes

Imported efficacy for tiers two and three. Each entry needs the population, the outcome
definition, the effect size with its interval, and the citation. An effect size without a
matching population is not usable.

### Education, tier one causal anchor

| Field | Value |
|---|---|
| Study | OPEN |
| Participant level data available | OPEN |
| Licence permits public analysis | OPEN |

This is the item that determines whether the project has a tier one rung at all. Until it
is closed, all three domains sit at tier two and `docs/00_method.md` section 4 overstates
what the project can claim.

### Academic medical centers, care coordination

| Field | Value |
|---|---|
| Trials | OPEN |
| Population | OPEN |
| Outcome definition | OPEN |
| Effect size and interval | OPEN |

### Advancement, fundraising field experiments

| Field | Value |
|---|---|
| Trials | OPEN |
| Population | OPEN |
| Outcome definition | OPEN |
| Effect size and interval | OPEN |

---

## Context figures

Figures used in framing rather than analysis. These appear in prose and must be sourced
before any public document quotes them.

| Figure | Used for | Source | Status |
|---|---|---|---|
| National completion and retention rates | Framing the scale of the problem | | OPEN |
| Typical gift officer portfolio size | Framing capacity in advancement | | OPEN |
| Typical advisor caseload | Framing capacity in education | | OPEN |

---

## Figures computed in this repository

These are not sourced externally. They are produced by scripts and traceable to them.

| Figure | Value | Script |
|---|---|---|
| Registrations in OULAD | 32,593 | `01_data_profile.py` |
| Raw withdrawal rate | 31.16% | `01_data_profile.py` |
| Analysis population after exclusions | 29,914 | `02_cohort.py` |
| Withdrawal rate in analysis population | 24.71% | `02_cohort.py` |
| Withdrawal range across module presentations | 6.93% to 46.38% | `01_data_profile.py` |
| Clickstream rows | 10,655,280 | `01_data_profile.py` |

Any figure quoted in a public document must appear either in this table or in a cache
file written by a numbered script.
