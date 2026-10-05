/* ==========================================================================
   MARGINAL — content
   Plain language. No script names, no file paths, no statistics jargon in
   anything a reader sees. Copy lives here; numbers never do.
   ========================================================================== */

export const STRATEGIES = [
  { key: "risk", label: "Who is most likely to give",
    question: "Who looks like a donor?", short: "likely",
    note: "The people a standard prediction model puts at the top." },
  { key: "effect", label: "Who a visit would change",
    question: "Whose mind would a visit change?", short: "changed",
    note: "The people whose decision the visit is estimated to alter." },
  { key: "historical", label: "Who gets visited today",
    question: "Where does officer time go now?", short: "today",
    note: "The pattern the existing programme already follows." },
  { key: "oracle", label: "Perfect hindsight",
    question: "What if we knew the true outcome?", short: "perfect",
    benchmark: true,
    note: "Knowable only because this population is invented. No real institution could build this list." }
];

export const HOSPITAL_LISTS = [
  { key: "steadier", label: "The steadier model", question: "Sorts slightly worse, keeps most of its list when rebuilt",
    short: "steadier" },
  { key: "accurate", label: "The more accurate model", question: "Sorts better, keeps less of its list when rebuilt",
    short: "accurate" }
];

// The fundraising chapter has to be readable as two kinds of thing at once: results
// the analysis produced, and settings that were chosen because no published figure
// pins them down. A reader should never have to guess which is which.
//
// No published figure is quoted here. Sector figures were considered as context, but
// their citations were never completed, so none of them appears on the page. See the
// sources register.
export const EVIDENCE = {
  sourced: {
    label: "From the analysis",
    tip: "Produced by the model runs behind this page. Rerunning from the same starting " +
         "point gives the same number."
  },
  fixed: {
    label: "Chosen, not measured",
    tip: "A setting the simulation needs and no data can supply. Held fixed and stated " +
         "here rather than hidden."
  },
  illustrative: {
    label: "Chosen, not measured",
    tip: "No published figure pins this down, so it is varied across a wide range and the " +
         "conclusion is reported against that range."
  },
  invented: {
    label: "Invented population",
    tip: "These people do not exist. That is deliberate: it is the only way to know what " +
         "each of them would have done both with help and without it."
  }
};

export const FUNDRAISING_EVIDENCE = [
  { k: "sourced", what: "Every result on this page",
    detail: "Which people each approach picks, and what each approach achieved. All of it " +
            "comes out of the model runs, not out of this page." },
  { k: "invented", what: "The people themselves",
    detail: "All 50,000 are generated. In return we know, for every one of them, what " +
            "they would have done if visited and if left alone. No real dataset can tell " +
            "you both." },
  { k: "illustrative", what: "How much a visit changes anyone",
    detail: "No published estimate we could find says what one visit does to one person, " +
            "and that is the number this would need. So it is varied from nothing to " +
            "twice the baseline, and the finding is reported across that whole range." },
  { k: "fixed", what: "Where the major gift line sits",
    detail: "Gifts above $25,000 count as major here. That is one choice of where to draw " +
            "the line, not a definition any body sets." },
  { k: "illustrative", what: "How many people a visit puts off",
    detail: "Varied from nobody to one in five. This turns out to be the setting the " +
            "entire comparison depends on." },
  { k: "illustrative", what: "How many people can be reached",
    detail: "125 per officer, and one in every thirty-three people overall. Varied from " +
            "one to twenty percent throughout." }
];

export const COPY = {
  brand: "MARGINAL",
  tagline: "Allocation under constraint",
  heroQuestion: "Who gets the help?",
  heroLede:
    "Every institution with a waiting list has to choose. Pick the people who look " +
    "most likely to act and you get one list. Pick the people your effort would " +
    "actually change and you get a different one. Almost none of the same names appear " +
    "on both. When capacity is scarce, choosing who to contact is itself the " +
    "allocation decision.",
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
    people: {
      // {howDifferent} is chosen from the overlap at the capacity on screen, so the
      // sentence stays true as the reader moves the control.
      claim: "The same amount of outreach reached {howDifferent} people.",
      figure: "{jaccard}",
      figureNote: "of the two lists are the same people",
      read: "Both approaches contact the same number of prospects. The less room there " +
            "is, the less they agree about which ones."
    },
    outcome: {
      claim: "Choosing on who a visit would change produced more gifts than choosing on who looks likely.",
      figure: "{effect}",
      figureNote: "additional gifts caused, against {risk} the other way",
      read: "Gifts that happened because of the visit, not gifts the visit happened to " +
            "sit beside."
    },
    representation: {
      claim: "The people who look like donors are largely not the people worth visiting.",
      figure: "{hist}",
      figureNote: "of today's list already gives, against {oracle} of the best possible list",
      read: "Current practice concentrates on existing donors. The value sits with people " +
            "who have never given."
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
        "The more accurate model sorted patients better, but each rebuild on a slightly " +
        "different sample swapped out a substantial share of its list, while the steadier " +
        "model kept most of its own. The number either one would report barely moved."
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
