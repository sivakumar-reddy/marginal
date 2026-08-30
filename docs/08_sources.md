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
| Data use agreement for required tables | CONFIRMED. Credentialed access covers the full MIMIC-IV release, not the emergency department module alone. |
| Version | OPEN |
| Retrieved | OPEN |
| Required citation | OPEN |

### Advancement domain population

Constructed, not observed. No public individual level donor portfolio dataset is known
to exist, which is itself an OPEN claim requiring verification.

Parameters fall into two categories and the distinction is load bearing. Sector evidence
provides context for whether the exercise is realistic. It does not supply the causal
quantities the simulation needs, and it is not treated as though it does.

#### Category A. Sector evidence, contextual only

Reported from CASE and VSE material. **Each entry needs a specific citation before any
public document quotes it: publication, year, and page or URL. Until that is recorded the
entry is not usable in a public claim.**

| Figure | Reported value | Citation | Status |
|---|---|---|---|
| Prospects per development officer | approximately 55, Vanderbilt example | | CITATION INCOMPLETE |
| Conversion, phone solicitation example | approximately 30% | | CITATION INCOMPLETE |
| Major gift solicitation yield | reported examples exist | | CITATION INCOMPLETE |
| Leadership donor retention | reported examples exist | | CITATION INCOMPLETE |
| Major gift threshold convention | $25,000 appears as an institutional convention | | CITATION INCOMPLETE |
| Total funds received, sector | | | OPEN |
| Alumni, non alumni and individual giving composition | | | OPEN |
| Donor concentration | | | OPEN |

Notes on use.

The 55 prospects per officer figure is an external reference point, not the simulation
parameter. The simulation uses 125 per officer, which is an illustrative high capacity
scenario. Portfolio size varies substantially by institution and by how a prospect is
defined, so neither number is a universal benchmark.

The $25,000 threshold is a defensible institutional convention, not a universal
definition. No claim is made that the sector defines all major gifts at that level.

The conversion, yield and retention examples are institutional illustrations. They are
NOT transplanted into the individual level causal generator. A rate observed at one
institution under one programme does not identify an individual treatment effect.

Donor concentration evidence is the most useful item here, because it supports the
premise the whole project rests on: that prioritisation matters when a small share of
constituents accounts for a large share of giving.

#### Category B. Illustrative parameters, swept not asserted

No sector benchmark identifies these. Each is varied across a wide range so the
conclusion can be read against the assumption rather than resting on it.

| Parameter | Value used | Swept over | Why it cannot be sourced |
|---|---|---|---|
| Prospect pool size | 50,000 | scale only | an institutional choice, not a benchmark |
| Portfolio capacity | 3%, 1,500 of 50,000 | 1, 3, 5, 10, 20% | depends on institution and prospect definition |
| Treatment effect magnitude | see generator | 0 to 2.0 | no published estimate identifies the individual causal effect of a visit |
| Harm severity | see generator | 0 to 2.0 | no published estimate identifies it |
| Harm prevalence, do not disturb share | 8% | 0, 5, 8, 12, 20% | the 8% was arbitrary and is not presented as established |
| Group shares, other three | see generator | held in proportion | asserted structure, not measured |
| Observability of latent traits | baseline | 0 to 1.0 | describes the value of better intelligence in principle |
| Outcome horizon | within the modelled period | not swept | no defensible sector convention identified |
| Gift amount distribution | lognormal, see generator | not swept | shape asserted for plausibility only |

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
| Trials | NONE IDENTIFIED |
| Population | n/a |
| Outcome definition | n/a |
| Effect size and interval | n/a |

No defensible published estimate of the individual causal effect of a personal
solicitation or officer visit has been identified in CASE or VSE material. The effect
model is therefore synthetic and its magnitude is swept rather than estimated. This is
stated as a limitation in the domain's own documentation and on the public page. It is
not a gap to be filled by borrowing a related statistic.

---|---|
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
| Typical gift officer portfolio size | Framing capacity in advancement | CASE, Vanderbilt example, approximately 55 | CITATION INCOMPLETE |
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
