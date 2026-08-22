# 00. Method

Status: draft. Written before any data was loaded or any model was fit.

This document states what the project asks, what it will and will not claim, and how
each claim will be tested. It is written first so that the analysis cannot be shaped
after the fact to fit a result. Where a figure appears anywhere in this repository, it
must be traceable to a script in `src/`. Figures quoted from memory or from secondary
sources are marked as unverified until a script or a citation replaces them.

---

## 1. The question

Institutions that serve a population and intervene in it face a shared constraint. An
academic advisor can hold a limited weekly caseload. A gift officer carries a portfolio
of roughly a hundred to a hundred and fifty prospects. A care coordinator at an academic
medical center manages a panel of fixed size. In every case the population needing
attention exceeds the capacity to give it, and someone must decide who receives it.

The near universal practice is to rank the population by predicted risk of an adverse
outcome and to work down that list until capacity is exhausted. Retention analytics
produce risk scores. Wealth screening produces capacity ratings. Readmission models
produce risk deciles. The ranking object is the same in all three, and so is the
implied decision rule.

This project asks whether that rule is correct.

The quantity that determines the value of contacting a person is not their probability
of a bad outcome. It is the amount by which contact changes that probability. These two
quantities are different, and ranking by one is not equivalent to ranking by the other
except under a specific and rarely stated condition, given in section 3.

The question this project answers is therefore:

> Under a fixed capacity constraint, how far apart are the ranking produced by predicted
> risk and the ranking produced by predicted marginal effect, and under what conditions
> does that gap matter enough to change practice?

---

## 2. Non claims

These are stated before the claims, and they are binding.

**This project does not claim to identify causal treatment effects in every domain.**
Only one of the three domains rests on participant level random assignment. The other
two import an effect size from published research and impose an assumed heterogeneity
structure. Any statement derived from those two domains is conditional on that imported
structure and will be labelled as such at the point of use, not in a footnote.

**This project does not claim that risk ranking is always wrong.** Section 3 gives the
exact condition under which risk ranking is optimal. Part of the contribution is
identifying when that condition holds, not asserting that it never does.

**This project does not claim to predict individual outcomes.** Individual level
predictions are inputs to an allocation decision studied in aggregate. No claim is made
about the accuracy of any single prediction, and no interface will present one as
actionable for a named person.

**This project does not claim its findings transfer to any specific institution.** The
education data comes from a distance learning provider whose attrition dynamics differ
from those of a residential campus. The clinical data comes from a single academic
medical center. The advancement population is constructed. Transfer is a hypothesis this
project raises, not a result it establishes.

**This project does not claim novelty in method.** Uplift modelling and heterogeneous
treatment effect estimation are established fields. The contribution is applying them to
a capacity constrained allocation decision across three sectors that share the structure
and comparing what survives as evidence quality degrades.

**No result will be reported without its uncertainty.** Point estimates of ranking
divergence are meaningless without an interval, because the divergence can be produced
by estimation noise alone. Section 6 specifies the null model against which every
divergence figure is tested.

---

## 3. The decision problem

Let a population of size N be indexed by i. Let Y denote a binary adverse outcome:
withdrawal, non renewal of a gift, an unplanned readmission.

For each person define two quantities.

Baseline risk:

    r_i = P(Y_i = 1 | no intervention)

Marginal effect of intervention:

    tau_i = P(Y_i = 1 | no intervention) - P(Y_i = 1 | intervention)

Capacity is a fixed integer k, far smaller than N. Two candidate allocations follow.

    R_k = the k people with the largest r_i
    E_k = the k people with the largest tau_i

Expected adverse outcomes averted under an allocation S is the sum of tau_i over i in S.
By construction E_k maximises this quantity. R_k does not, unless the two sets coincide.

**The condition under which they coincide.** R_k equals E_k for all k precisely when
tau_i is a monotone increasing function of r_i. This is not a technicality. It is the
hinge of the entire project, and it is an assumption practitioners make without
articulating it.

Two efficacy models make the stakes concrete.

*Constant relative risk reduction.* If intervention multiplies risk by a factor c less
than one, then tau_i equals r_i times one minus c. Effect is strictly increasing in
baseline risk. Risk ranking is optimal, and this project's thesis is false in that
domain. This case must be reported honestly wherever it holds.

*Bounded absolute effect with saturation.* If intervention can shift risk by at most a
fixed amount, and if people at very high risk are subject to causes the intervention
does not touch, then tau_i rises with r_i and then falls. Effect is single peaked in
baseline risk. Risk ranking systematically selects people past the peak, and the two
lists diverge.

The empirical question is which of these the data supports. Domain one can answer it.
Domains two and three test whether the conclusion survives when the shape must be
assumed rather than estimated.

---

## 4. The evidence ladder

Revised 2026-08-23, after the search recorded in `docs/08_sources.md` returned no usable
participant level randomised education experiment. The original version of this section
placed education at a tier where treatment effects would be identified from data. That
tier does not exist for this project and the claim has been withdrawn.

### 4.1 Why there is no identified tier

The search covered ICPSR, filtered to studies rather than publications, across two query
families. Seventeen studies were returned. The closest match by design was ICPSR 120838,
Stay the Course, a multi armed randomised controlled trial of intensive case management
at Tarrant County College, Fort Worth, 2013 to 2016. Its deposit contains Stata code and
a ReadMe. It contains no data. The underlying records are proprietary administrative data
held by the college's Office of Institutional Research, a second dataset is held by
Catholic Charities Fort Worth, and treatment status can only be reconstructed if the
college authorises release of the original student identifier ordering, because the code
recovers assignment from row order rather than a stored variable.

That is three institutional approvals, two of them by postal request. It is not
obtainable by an unaffiliated analyst and it is not obtainable quickly by anyone.

This is not an accident of one archive. Student records are protected, so education
trials deposit code and retain data behind institutional agreements. The absence is
structural, and it is the same absence every practitioner faces.

### 4.2 The revised ladder

All three domains import efficacy. None estimates it. What separates them is how much of
the rest is real.

**Tier one. Real population, effect imported from a randomised trial in a comparable
setting.**
Individual level records exist for a real population. The average effect is taken from a
published trial whose intervention and outcome resemble the one being modelled, and a
heterogeneity structure is imposed and swept. The population is measured; the effect is
borrowed; the shape of the effect is assumed.

**Tier two. Real population, effect imported from trials in a less comparable setting.**
As above, but the trial population differs more from the one being modelled, so the
imported effect carries more transfer risk. The gap between tier one and tier two is the
strength of the analogy, not the presence of data.

**Tier three. Constructed population, effect imported.**
No public individual level data exists. The population is generated from published
aggregate benchmarks with every parameter traceable to a script. Both the population and
the effect are assumptions.

### 4.3 What the ladder now tests

The original framing asked how far down the ladder a finding established at the top
survives. With no identified tier, that question cannot be asked and is withdrawn.

The question the revised ladder answers is narrower and, on reflection, closer to what
matters. Every institution allocating a scarce intervention is working with a measured
population and a borrowed effect. None has a trial of its own programme on its own
people. The project therefore asks:

> Given that efficacy must be assumed, how much does the allocation decision depend on
> which assumption is made, and how much does that dependence change as the rest of the
> evidence degrades?

This is answerable with what is available, and it describes the real decision. A finding
that required an identified treatment effect would have been a finding no practitioner
could act on.

### 4.4 What this costs

Stated plainly rather than buried.

The project cannot say that effect ranking beats risk ranking. It can say that the two
rankings diverge, that the divergence exceeds the instability of the ranking itself over
a stated region of the assumption space, and that the choice between them turns on a
parameter nobody has measured.

It cannot estimate how effects vary across people. The efficacy family used is a function
of baseline risk alone, which bounds the divergence attributable to shape and excludes
covariate driven heterogeneity entirely. Stay the Course reports significant effects for
women and imprecise estimates for the full sample, which is direct evidence that
covariate driven heterogeneity exists in exactly this kind of intervention. The project
cites that and cannot measure it.

Any future access to participant level trial data would upgrade the education domain and
change what section 7 can falsify. Until then, no result in this repository may be
described as causal.

---

## 5. Domains

### 5.1 Education. Tier one.

Operational population: the Open University Learning Analytics Dataset. Roughly thirty
thousand student registrations with weekly interaction records, demographics and
assessment results. Withdrawal is directly observed.

OULAD contains no intervention assignment. It therefore supplies the population, the
feature structure and the realistic risk model, but cannot supply tau.

Efficacy is imported from Stay the Course (ICPSR 120838), a multi armed randomised
controlled trial of intensive case management at Tarrant County College, 2013 to 2016.
That trial supplies an average effect for a caseworker assigned to a student, which is
structurally the intervention this domain models. Its participant level data is not
obtainable; see section 4.1. The effect is therefore a published number, not an estimate
produced here.

This places education at tier one because the population is real and individual level and
the borrowed effect comes from a genuinely comparable intervention. It does not place it
at any tier where the effect is identified, because no such tier exists in this project.

The transfer risk is stated rather than minimised. Stay the Course is US community
college; OULAD is UK distance learning. The intervention differs in intensity and the
outcome definitions are not identical. Any figure derived from the imported effect
carries that gap, and the sensitivity sweep exists because of it.

Prediction is time sliced. Risk models are fit using only information available at weeks
four, eight and twelve of a module presentation, so that no feature can encode the
outcome it is predicting.

### 5.2 Academic medical centers. Tier two.

Operational population: MIMIC-IV. Credentialed access is held. The data use agreement
covering the specific tables required must be confirmed before extraction.

Scope note. This domain is academic medical center care panels, not care management in
general. The narrowing is deliberate and affects the framing, the implementation brief
and the intended reader.

Effect sizes are imported from published care coordination and transitional care trials.
Heterogeneity is imposed under the two structures in section 3 and swept.

### 5.3 Advancement. Tier three.

No public donor portfolio dataset exists at individual level. This claim is under
verification. See section 8.

The population is constructed from published aggregate benchmarks on giving
distributions, retention rates and portfolio sizes. Construction is fully documented and
the generating script is the sole source of every parameter. The constructed nature of
this population is stated in the README, on the site, in the implementation brief and at
every point a figure from it appears. It is never presented as observed data.

Current practice in this sector ranks prospects by capacity to give, which is a wealth
proxy rather than a risk score, and is further from effect ranking than either of the
other two domains. This makes advancement the domain where the gap between practice and
optimum is expected to be largest and the evidence for it weakest at the same time. That
tension is the reason the domain is included, not a reason to exclude it.

---

## 6. The overlap statistic

The headline quantity, computed identically in all three domains.

For capacity k:

    O(k) = |R_k intersect E_k| / k

Reported alongside it, and required for interpretation:

**Value gap.** The expected outcomes averted under E_k minus those averted under R_k,
expressed as a proportion of the E_k value. This is what the divergence costs. A large
O(k) gap with a negligible value gap is not a finding worth acting on, and must not be
presented as one.

**Null distribution.** O(k) is compared against the overlap produced when tau is replaced
by a random permutation preserving its marginal distribution, and against the overlap
produced by two independent bootstrap refits of the same model. The second is the
important one. If two refits of the effect model on resampled data disagree with each
other as much as risk ranking and effect ranking disagree, the divergence is estimation
noise and the project has no result. This test is pre committed here and will be
reported whether or not it is passed.

**Capacity curve.** O(k) traced across the full range of k, since divergence is expected
to be largest at small k and to vanish as k approaches N.

---

## 7. What would falsify the thesis

Stated in advance.

The thesis fails if the estimated tau is monotone increasing in r in domain one, because
that makes risk ranking optimal on real data.

The thesis fails if the value gap is small at realistic capacity levels even when O(k) is
low, because that means the two lists differ in membership without differing in
consequence.

The thesis fails if the bootstrap refit overlap is comparable to the risk versus effect
overlap, because that means the divergence is noise.

The thesis is weakened, but not destroyed, if it holds at tier one and disappears at
tiers two and three. That result would itself be worth reporting: it would mean the
divergence is only visible where a comparable trial exists to borrow from, which is a
finding about which institutions can even ask the question.

---

## 8. Verification queue

Open items. None of the following may be treated as established until closed. Each
requires a source and a date recorded in `docs/08_sources.md`.

1. CLOSED 2026-08-23. No participant level randomised education experiment is
   obtainable. See section 4.1 and `docs/08_sources.md`. Section 4 was rewritten as a
   result. Reopen only if institutional access to trial microdata becomes available.
2. Confirmation that the held MIMIC-IV credential covers the specific tables required,
   and that the applicable data use agreement is signed.
3. Published effect sizes for care coordination interventions at academic medical
   centers, with population and outcome definitions specific enough to import.
4. Published effect sizes from fundraising field experiments, same requirement.
5. The claim that no public individual level donor portfolio dataset exists.
6. National completion and retention rates, if any are to be cited in public material.
7. Typical gift officer portfolio size, if cited.
8. OULAD withdrawal rate. To be computed in `src/`, never quoted.

---

## 9. Out of scope

No tool accepting institutional data. No authentication, storage or upload. The
interactive artefact serves precomputed results only.

No recommendation is made about any named individual.

No claim about fairness or disparate impact of the allocation rules is made unless a
dedicated analysis supports it. Reallocating attention away from the highest risk group
has distributional consequences that deserve their own treatment rather than a passing
sentence, and if that analysis is not done, its absence is stated in the limitations.

The visa related reasoning behind the choice of sectors does not appear in the README,
on the site or in any public document. The domains stand on the shared allocation
structure, which is sufficient.
