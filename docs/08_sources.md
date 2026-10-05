# 08. Sources

Every dataset, benchmark and published figure the project depends on. Nothing may be
cited anywhere in this repository unless it appears here with a source and a date.

Items marked OPEN are unverified. Claims resting on them are not defensible until closed.

## Publication status

Checked 2026-10-05, before the public release of the site.

The public page quotes exactly two external sources: OULAD and MIMIC-IV, each with the
citation its provider requires, in the page footer. Both are CLOSED below. Every other
figure on the page is computed in this repository.

Nothing else in this register is quoted on the public page. Items still OPEN or
CITATION INCOMPLETE below are recorded so the gap is visible; they block publication
only if they are quoted somewhere public, including in posts about the project.

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
| Licence | CC BY 4.0, Creative Commons Attribution 4.0 International. CLOSED. |
| Licence source | https://research.stem.open.ac.uk/ouanalyse/open-dataset-more/, checked 2026-10-05 |
| Required citation | Kuzilek J., Hlosta M., Zdrahal Z. Open University Learning Analytics dataset Sci. Data 4:170171 doi: 10.1038/sdata.2017.171 (2017). Verbatim from the page above. CLOSED. |
| Attribution on the site | Footer: citation, DOI link, licence link, and a statement that the figures are derived from the dataset. CC BY 4.0 makes attribution a condition of use. |

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
| Licence | PhysioNet Credentialed Health Data License 1.5.0 |
| Module and tables used | hosp: `admissions`, `diagnoses_icd`, `patients`, `services`. No table from MIMIC-IV-ED is read by any script in this project. |
| Version | 3.1, released 2024-10-11. CLOSED. |
| Retrieved | 2026-08-22, from the local file timestamps. CLOSED. |
| Evidence for the version | v3.1 was the current release on the retrieval date, and `admissions.csv.gz` has 546,028 rows, consistent with the v3 series. To make this definitive, compare the hashes below with `SHA256SUMS.txt` on the v3.1 file page while signed in to PhysioNet. |
| SHA256, admissions.csv.gz | A9584ED88E9ED664A2F66F86A5CF9FD175C8BB0AF50E3B6115598B19E978384E |
| SHA256, diagnoses_icd.csv.gz | 47665A41B2A3AD990D6F314062D5BD6D29D467B0FD402DD94662044EC8B073D2 |
| SHA256, patients.csv.gz | 4C7507DE7ECAD8C5BA7647EA4D26018E88FF6672C5FC22AB59C2A5697D687CDD |
| SHA256, services.csv.gz | 31C82EBEE94E0C04D6966FBFEC30579EC00F9C7816B80852F9580656E6183888 |
| Required citation, dataset | Johnson, A., Bulgarelli, L., Pollard, T., Gow, B., Moody, B., Horng, S., Celi, L. A., & Mark, R. (2024). MIMIC-IV (version 3.1). PhysioNet. RRID:SCR_007345. https://doi.org/10.13026/kpb9-mt58. CLOSED. |
| Required citation, paper | Johnson, A.E.W., Bulgarelli, L., Shen, L. et al. MIMIC-IV, a freely accessible electronic health record dataset. Sci Data 10, 1 (2023). https://doi.org/10.1038/s41597-022-01899-x. CLOSED. |
| Required citation, PhysioNet | Pollard, T., Moody, B. E., Lehman, L., Gow, B., Fernandes, C., Xie, C., Johnson, A., Mark, R. G., & Heldt, T. (2026). PhysioNet as a global platform for biomedical research. Nature Health. https://doi.org/10.1038/s44360-026-00096-z. CLOSED. |
| Citation source | https://physionet.org/content/mimiciv/, checked 2026-10-05 |

**Licence obligations that bear on publication.** Clause 2: avoid disclosing the
identity of any individual or institution referenced in the data. Clause 3: do not
share access to restricted data. Clause 8: contribute code associated with
publications arising from the data to a repository open to the research community.

**What the public site contains from this dataset.** For a random sample of 1,200
held-out admissions, one bitmask per admission recording which lists selected it. No
identifiers, no clinical values, no outcomes. Everything else is aggregate.

**Removed before publication, 2026-10-05.** The site export previously carried three
per-admission arrays for the same sample: the 30-day readmission outcome, insurance
category and discharge location. The page never read them. They were removed from
`17c_mimic_roster.py` at the source, the export was regenerated and checked identical to
the stripped file, and every earlier version of `site/data/marginal.json` was purged
from git history before any remote existed.

**Code publication.** Clause 8 is met when this repository, without data, is public.
Record the repository URL here when it is.

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

**Status, 2026-10-05.** None of these is quoted on the public page. An earlier version of
the page quoted the phone conversion, solicitation yield and retention examples under a
"Published figure" label; those rows were removed because their citations were never
completed. The $25,000 threshold now appears on the page only as a disclosed choice,
recorded in Category B.

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
| Major gift threshold | above $25,000 | not swept | a choice of where to draw the line; shown on the page as chosen, not measured, with no claim that any body defines it |

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
abstract. Not quoted on the public page as of 2026-10-05.

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

Not used on the public page. The hospital chapter makes no claim about who benefits.

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

---

## Context figures

Figures used in framing rather than analysis. These must be sourced before any public
document quotes them. None is quoted on the public page as of 2026-10-05.

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
| MIMIC-IV admissions in the hospital cohort | 321,547 | `17c_mimic_roster.py` |
| MIMIC-IV admissions held out for scoring | 64,093 | `17c_mimic_roster.py` |

Any figure quoted in a public document must appear either in this table or in a cache
file written by a numbered script.
