/* ==========================================================================
   MARGINAL — content
   Plain language. No script names, no file paths, no statistics jargon in
   anything a reader sees. Copy lives here; numbers never do.
   ========================================================================== */

export const STRATEGIES = [
  { key: "risk", label: "Most likely to give",
    question: "Who looks like a donor?", short: "likely",
    note: "The people a normal prediction model puts at the top." },
  { key: "effect", label: "Most likely to change",
    question: "Who would a visit actually move?", short: "movable",
    note: "The people whose decision a visit is estimated to change." },
  { key: "historical", label: "Who we visit today",
    question: "Where does officer time go now?", short: "today",
    note: "The pattern the existing programme follows." },
  { key: "oracle", label: "Perfect hindsight",
    question: "Who should have been visited?", short: "perfect",
    benchmark: true,
    note: "Only knowable because this population is invented. No real institution could build this list." }
];

export const HOSPITAL_LISTS = [
  { key: "steadier", label: "The steadier model", question: "Sorts a little worse",
    short: "steadier" },
  { key: "accurate", label: "The more accurate model", question: "Wins every accuracy test",
    short: "accurate" }
];

// The fundraising chapter has to be readable as two kinds of thing at once: results
// the analysis produced, and settings that were chosen because no published figure
// pins them down. A reader should never have to guess which is which.
export const EVIDENCE = {
  sourced: {
    label: "From the analysis",
    note: "Produced by the model runs on this page. Reproducible from a fixed starting point."
  },
  verified: {
    label: "Published figure",
    note: "Traced to a named publication. Context for whether the exercise is realistic. " +
          "None of these sets a number in the simulation."
  },
  illustrative: {
    label: "Chosen, not measured",
    note: "No published figure identifies this, so it is varied across a wide range " +
          "rather than asserted. The conclusion is reported against the range."
  }
};

export const FUNDRAISING_EVIDENCE = [
  { k: "illustrative", what: "How many people there are, and how many can be reached",
    detail: "50,000 people and room for 1,500. Portfolio sizes vary widely by institution " +
            "and by what counts as a prospect, so this is one scenario among many. Capacity " +
            "is varied from 1 to 20 percent throughout." },
  { k: "illustrative", what: "How much a visit changes anyone",
    detail: "No published study identifies how much one visit changes one person's decision. " +
            "It is varied from nothing to twice the baseline, and the finding is reported " +
            "across that whole range." },
  { k: "illustrative", what: "How many people a visit puts off",
    detail: "Set at 8 in 100 with no external basis, and varied from nobody to 1 in 5. " +
            "This turns out to be the setting the whole comparison depends on." },

  { k: "verified", what: "What published sources say about fundraising",
    detail: "About 30 in 100 people give when reached by phone, across the sector. At one " +
            "large university, just over half of major gift asks succeeded. At one " +
            "foundation, 82 in 100 leadership donors gave again. Three of these describe " +
            "single institutions, not the sector. None of them says what one visit does " +
            "to one person, which is the number this page would actually need." },
  { k: "verified", what: "Where the $25,000 line comes from",
    detail: "Published profiles describe institutions treating gifts above $25,000 as " +
            "major. This page uses that figure because those conventions exist, not " +
            "because any body defines it that way." },
  { k: "illustrative", what: "How big a gift officer's list is",
    detail: "125 people per officer, chosen for this exercise. A candidate published " +
            "figure was reviewed and left out because its source could not be pinned " +
            "down, so nothing here claims what real portfolios look like." },
  { k: "sourced", what: "Everything on the chart and in the table",
    detail: "Every result shown here came out of the model runs, including which people " +
            "each approach selects and what each one achieved." }
];

export const COPY = {
  brand: "MARGINAL",
  tagline: "Allocation under constraint",
  heroQuestion: "Who gets the help?",
  heroLede:
    "Every institution with a waiting list has to choose. Pick the people who look " +
    "most likely to act and you get one list. Pick the people your effort would " +
    "actually change and you get a different one. Almost none of the same names appear " +
    "on both.",
  scarcity:
    "A university fundraising office has {pop} people it could contact and enough " +
    "officer time for {k}. Someone has to choose.",

  explore: {
    eyebrow: "The choice",
    title: "The same people, sorted four ways",
    lede:
      "Every mark is one person. Solid marks are the ones that approach would contact. " +
      "Pink marks are people who give less after being contacted than they would have " +
      "if left alone.",
    capacityPrompt: "How many can you reach?"
  },

  reveals: {
    people: { pre: "Same number of visits.", post: "Only {jaccard} of the same people." },
    outcome: { pre: "Different result.", post: "{effect} extra gifts instead of {risk}." },
    representation: {
      pre: "Different people entirely.",
      post: "{hist} of today's list already gives. The list that would have worked best is {oracle}."
    }
  },

  domains: {
    eyebrow: "Three places this happens",
    title: "The same problem, three institutions",
    lede:
      "Two of these use real records from real institutions, and neither can tell us " +
      "who was actually helped, because nobody ran an experiment. The third is invented, " +
      "which is exactly why it can. That trade is the honest shape of this problem."
  },

  chapterCopy: {
    education: {
      n: "01",
      label: "A university",
      what: "Students at risk of dropping out",
      action: "An advisor reaching out",
      finding: "Waiting for more information did not produce a better list.",
      body:
        "Advisors could act on day one, or wait twelve weeks and know far more about " +
        "each student. Tested on students the model has never seen, the extra twelve " +
        "weeks changed accuracy by less than the run to run noise, while more than half " +
        "the students who eventually left had already gone. One course above shows a " +
        "larger gain; across all of them it does not survive."
    },
    clinical: {
      n: "02",
      label: "A teaching hospital",
      what: "Patients likely to come back within a month",
      action: "Enrolment in a follow-up care programme",
      finding: "The total held steady. The names underneath it did not.",
      body:
        "The more accurate model won on every standard measure and produced a list that " +
        "changed almost completely each time it was rebuilt, while the number it " +
        "reported barely moved."
    },
    clinicalReveals: {
      people: "Rebuild the more accurate model on a slightly different sample and {churn} of its list changes.",
      steady: "Rebuild the steadier one and {steady} changes.",
      report: "The number the ward reports moves {spread}. The people receiving care move far more."
    },
    advancement: {
      n: "03",
      label: "A fundraising office",
      what: "People who might make a gift",
      action: "A visit from a gift officer",
      finding: "Here we know the right answer, and every workable method misses most of it.",
      body:
        "This population is invented, so we know what each person would have done both " +
        "with a visit and without one. That makes it the only place where each approach " +
        "can be graded against the truth. The catch is that the things a fundraising " +
        "database actually records explain almost none of the difference between people, " +
        "so the limit is the information, not the method."
    }
  },

  method: {
    eyebrow: "If you want to check the work",
    title: "How this was built, and what would break it",
    lede:
      "None of this is needed to follow the argument above. It is here because the " +
      "argument should not be taken on trust."
  },

  trust: {
    observed: "Real institutional records",
    simulated: "Invented population, not real donors",
    benchmark: "Perfect hindsight. Not achievable."
  },

  states: {
    loading: "Loading the results",
    errorTitle: "Some results are missing",
    errorBody:
      "This page only shows numbers the analysis actually produced. The results file " +
      "needs to be rebuilt before the page can display them.",
    domainMissing:
      "This section is not in the current results. Nothing is shown in its place."
  },

  provenance: {
    headline: "Every number here came out of the analysis, not out of this page.",
    body:
      "Nothing is calculated in your browser and no figure was typed in by hand. Where " +
      "a number was missing, the space is left empty rather than filled with a guess."
  }
};

export const fmt = {
  // An em dash means the number is genuinely undefined, most often a statistic over
  // an empty set. It is never a stand-in for a value that failed to load.
  pct: (x, d = 1) => x == null || isNaN(x) ? "—" : (x * 100).toFixed(d) + "%",
  signed: (x, d = 0) => x == null || isNaN(x) ? "—" : (x > 0 ? "+" : "") + x.toFixed(d),
  int: x => x == null || isNaN(x) ? "—" : Math.round(x).toLocaleString(),
  tmpl: (s, vars) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "—")
};
