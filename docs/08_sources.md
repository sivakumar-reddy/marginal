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

### Education. Stay the Course

| Field | Value |
|---|---|
| Study | Increasing Community College Completion Rates among Low-Income Students: Evidence from a Randomized Controlled Trial Evaluation of a Case Management Intervention |
| Archive | ICPSR 120838, self-published, public record |
| Investigators | Sullivan, Kearney, Evans, Perry |
| Design | Multi armed RCT: intensive case management, emergency financial assistance only, control |
| Setting | Tarrant County College, Fort Worth, Texas, 2013 to 2016 |
| Outcomes | Continued enrolment and degree attainment, via National Student Clearinghouse |
| Reported effect | Significant increase in persistence and degree completion for women; full sample estimates imprecise. Associate degree receipt for women reported as tripled, 31.5 percentage points. No difference between the financial assistance only arm and control. Programme cost $4,343 per person. |
| Participant level data | NOT AVAILABLE |
| Retrieved | 2026-08-23 |

**Why the data is unavailable.** The ICPSR deposit contains six Stata do files and a
ReadMe, 180 KB, no data. Per the ReadMe, the underlying records are proprietary
administrative data held by Tarrant County College's Office of Institutional Research and
must be requested from them by post. Programme take up data must be separately requested
from Catholic Charities Fort Worth. Treatment status cannot be recovered from the files
at all unless the college authorises release of the original student identifier ordering,
because the Stata code identifies assignment by row position rather than a stored
variable.

**How it is used.** As an imported average effect and as documented evidence that
treatment effect heterogeneity exists in case management interventions. It is cited, not
re-analysed. The specific effect figures above must be verified against the published
paper before appearing in any public document; they are transcribed from the ICPSR
abstract.

### Education. Search record for participant level trial data

Run 2026-08-23. Recorded because the absence of an identified tier is a claim the project
makes, and a claim needs evidence.

| Field | Value |
|---|---|
| Archive searched | ICPSR |
| Queries | "college persistence randomized", "student retention experiment" |
| Filter | Studies tab, not Data-related publications |
| Studies returned | 4 and 17 respectively |
| Qualifying | None |

Failure modes observed: most results matched "retention" in the sense of teacher
retention or grade retention rather than student persistence; most carried RESTRICTED or
PARTIALLY RESTRICTED access; the single strong design match, ICPSR 120838, was code only.

The constraint appears structural rather than incidental. Student records are protected,
so education trials deposit replication code and retain data behind institutional
agreements. Harvard Dataverse and OSF were not exhausted. If this claim is challenged,
the honest answer is that the search was bounded at one hour across one archive and two
query families.

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
