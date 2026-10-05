/* ==========================================================================
   MARGINAL — application

   Three institutions are explorable. They ask the same question but the thing
   that varies is different in each, so the controls differ:

     university    a moment in the term. How much do you know yet?
     fundraising   nothing varies but the rule. Both know everything.
     hospital      the model is rebuilt. Does the same list come back?

   The visual grammar does not change between them. A mark is a person, a
   colour is an approach, pink is harm, dim is not selected.
   ========================================================================== */

import { Field, markColours, movementRibbon, droppedTone } from "./viz.js";
import { STRATEGIES, HOSPITAL_LISTS, COPY, EVIDENCE, FUNDRAISING_EVIDENCE, fmt }
  from "./content.js";

const $ = s => document.querySelector(s);

// Writing to a node that is not in the page should skip that element, not take the
// whole page down. A version mismatch between markup and script is a rendering gap,
// not a data problem, and must not be reported as one.
function setText(sel, value) {
  const el = $(sel); if (el) el.textContent = value; return !!el;
}
function setHTML(sel, value) {
  const el = $(sel); if (el) el.innerHTML = value; return !!el;
}
const $$ = s => [...document.querySelectorAll(s)];
const isNarrow = () => matchMedia("(max-width:900px)").matches;

// Resolve a design token. viz.js has its own copy; this is the app side, and both
// read the same custom properties so a colour is defined in exactly one place.
const css = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const UNI_LISTS = [
  { key: "analyst_a", label: "One analyst's list", question: "Who looks most at risk?", short: "analyst" },
  { key: "analyst_b", label: "A second analyst", question: "Same method, other half of the history", short: "second" },
  { key: "effect", label: "Who a conversation would change", question: "Whose mind would a conversation change?", short: "changed" }
];

const S = {
  data: null, domain: "advancement",
  adv: null, roster: null, cap: null,
  edu: null, day: null, eduCap: null,
  clin: null, clinCap: null, rebuild: 0,   // 0 means the model as first built
  focus: null, fields: new Map()
};

const bit = (m, i) => ((m >> i) & 1) === 1;

/* ---------- per domain accessors --------------------------------------- */

function lists() {
  if (S.domain === "education") return UNI_LISTS;
  if (S.domain === "clinical") return HOSPITAL_LISTS;
  return STRATEGIES;
}

// The hospital shows one estimator per panel. Which underlying list each panel draws
// depends on how many times the model has been rebuilt, so the mapping is dynamic.
function clinicalKey(panel) {
  if (S.rebuild === 0) return panel === "steadier" ? "risk" : "boosted";
  return panel === "steadier"
    ? `logit_rebuild_${S.rebuild}` : `boost_rebuild_${S.rebuild}`;
}
function frame() {
  if (S.domain === "education") return S.edu?.days?.[S.day]?.capacities?.[S.eduCap];
  if (S.domain === "clinical") return S.clin?.by_capacity?.[S.clinCap];
  return S.roster?.by_capacity?.[S.cap];
}
function listKeys() {
  if (S.domain === "education") return S.edu.lists;
  if (S.domain === "clinical") return S.clin.lists;
  return S.roster.strategies;
}
function dataKey(panelKey) {
  return S.domain === "clinical" ? clinicalKey(panelKey) : panelKey;
}
function harmedArray(f) {
  // the university has no harm channel: nobody is made worse by a conversation
  return f.harmed || null;
}

function selectionStats(key) {
  const f = frame(), i = listKeys().indexOf(dataKey(key)), harm = harmedArray(f);
  let sel = 0, h = 0;
  for (let j = 0; j < f.mask.length; j++) {
    if (!bit(f.mask[j], i)) continue;
    sel++; if (harm && harm[j]) h++;
  }
  return { sel, harm: h, harmShare: harm ? h / (sel || 1) : null };
}

function movement(a, b) {
  const f = frame(), ia = listKeys().indexOf(dataKey(a)), ib = listKeys().indexOf(dataKey(b));
  let entered = 0, left = 0, stayed = 0, A = 0, B = 0;
  for (let j = 0; j < f.mask.length; j++) {
    const x = bit(f.mask[j], ia), y = bit(f.mask[j], ib);
    if (x) A++; if (y) B++;
    if (x && y) stayed++; else if (y) entered++; else if (x) left++;
  }
  return { entered, left, stayed, jaccard: stayed / (A + B - stayed || 1) };
}

/* ---------- controls ---------------------------------------------------- */

function renderDomainSwitch() {
  const d = S.data.domains;
  const opts = [
    { k: "education", label: "A university", ok: d.education?.interactive },
    { k: "advancement", label: "A fundraising office", ok: d.advancement?.interactive },
    { k: "clinical", label: "A teaching hospital", ok: d.clinical?.interactive }
  ];
  setHTML("#domainSwitch", opts.map(o =>
    `<button data-d="${o.k}" aria-pressed="${o.k === S.domain}" ${o.ok ? "" : "disabled"}>
      ${o.label}${o.ok ? "" : '<span class="soon">not yet</span>'}</button>`).join(""));
  $$("#domainSwitch button").forEach(b => b.onclick = () => {
    if (b.disabled) return;
    S.domain = b.dataset.d;
    S.focus = lists()[0].key;
    S.rebuild = 0;
    S.fields.clear();
    $$("#domainSwitch button").forEach(x =>
      x.setAttribute("aria-pressed", String(x.dataset.d === S.domain)));
    renderRail(); wireFocus(); renderPanels(); renderFields({ animate: false });
    renderReveals(); renderTable(); renderEvidence();
  });
}

function renderRail() {
  const host = $("#rail");
  if (S.domain === "education") {
    host.innerHTML = `
      <span class="eyebrow" style="white-space:nowrap">How far into the term?</span>
      <div class="steps" id="steps" role="group" aria-label="Point in the term"></div>`;
    setHTML("#steps", S.edu.decision_days.map(d => `
      <button data-day="${d}" aria-pressed="${String(d) === S.day}">
        ${d === 0 ? "Day one" : "Week " + Math.round(d / 7)}
        <span class="sub">${d === 0 ? "registration only" : d + " days in"}</span></button>`).join(""));
    $$("#steps button").forEach(b => b.onclick = () => {
      S.day = b.dataset.day;
      $$("#steps button").forEach(x =>
        x.setAttribute("aria-pressed", String(x.dataset.day === S.day)));
      renderFields(); renderReveals(); renderTable();
    });
  } else if (S.domain === "clinical") {
    host.innerHTML = `
      <span class="eyebrow" style="white-space:nowrap">${COPY.explore.capacityPrompt}</span>
      <div class="capacity" id="capacity" role="group" aria-label="Capacity"></div>
      <div class="rebuild" style="width:100%;margin-top:14px">
        <button id="rebuildBtn">Rebuild both models</button>
        <span class="dots" id="rebuildDots"></span>
        <span class="which" id="rebuildWhich"></span>
      </div>`;
    $("#capacity").innerHTML = Object.keys(S.clin.by_capacity).map(c => {
      const pct = parseFloat(c) * 100;
      const op = Math.abs(parseFloat(c) - S.clin.headline_capacity) < 1e-9;
      return `<button data-cap="${c}" aria-pressed="${c === S.clinCap}">
        ${pct % 1 ? pct.toFixed(1) : pct}%<span class="op">${
          op ? "a typical programme" : fmt.int(S.clin.by_capacity[c].k) + " places"}</span></button>`;
    }).join("");
    $$("#capacity button").forEach(b => b.onclick = () => {
      S.clinCap = b.dataset.cap;
      $$("#capacity button").forEach(x =>
        x.setAttribute("aria-pressed", String(x.dataset.cap === S.clinCap)));
      renderFields(); renderReveals(); renderTable();
    });
    const n = S.clin.n_rebuilds;
    $("#rebuildBtn").onclick = () => {
      S.rebuild = (S.rebuild % n) + 1;
      renderFields(); renderReveals(); paintRebuild();
    };
    paintRebuild();
  } else {
    host.innerHTML = `
      <span class="eyebrow" style="white-space:nowrap">${COPY.explore.capacityPrompt}</span>
      <div class="capacity" id="capacity" role="group" aria-label="Capacity"></div>`;
    setHTML("#capacity", Object.keys(S.roster.by_capacity).map(c => {
      const pct = parseFloat(c) * 100;
      const op = Math.abs(parseFloat(c) - S.roster.headline_capacity) < 1e-9;
      return `<button data-cap="${c}" aria-pressed="${c === S.cap}">
        ${pct % 1 ? pct.toFixed(1) : pct}%<span class="op">${
          op ? "what they have" : fmt.int(S.roster.by_capacity[c].k) + " people"}</span></button>`;
    }).join(""));
    $$("#capacity button").forEach(b => b.onclick = () => {
      S.cap = b.dataset.cap;
      $$("#capacity button").forEach(x =>
        x.setAttribute("aria-pressed", String(x.dataset.cap === S.cap)));
      renderFields(); renderReveals(); renderTable();
    });
  }
}

function paintRebuild() {
  const n = S.clin?.n_rebuilds; if (!n) return;
  setHTML("#rebuildDots", Array.from({ length: n }, (_, i) =>
    `<span class="dot ${i + 1 === S.rebuild ? "on" : ""}"></span>`).join(""));
  setText("#rebuildWhich", S.rebuild === 0
    ? "as first built"
    : `rebuild ${S.rebuild} of ${n}, same data resampled`);
}

function wireFocus() {
  setHTML("#focus", lists().map(s =>
    `<button data-key="${s.key}" aria-pressed="${s.key === S.focus}">${s.short}</button>`).join(""));
  $$("#focus button").forEach(b => b.onclick = () => {
    S.focus = b.dataset.key;
    $$("#focus button").forEach(x =>
      x.setAttribute("aria-pressed", String(x.dataset.key === S.focus)));
    $$(".panel").forEach(p => p.classList.toggle("active", p.dataset.key === S.focus));
    const f = S.fields.get(S.focus); if (f) requestAnimationFrame(() => f.resize());
  });
}

/* ---------- fields ------------------------------------------------------ */

function renderPanels() {
  const L = lists();
  const n = ["", "one way", "two ways", "three ways", "four ways"][L.length] || `${L.length} ways`;
  setText("#exploreTitle", `The same people, sorted ${n}`);
  // Each institution has its own unit and its own channels. The hospital was
  // borrowing the fundraising lede and telling readers about gifts and visits.
  setText("#exploreLede",
    S.domain === "education"
      ? "Every mark is one student. Solid marks are the ones that approach would " +
        "contact. The first two fields are the same method on different halves of the " +
        "record; the third asks a different question. Nobody is made worse off by a " +
        "conversation, so there is no harm to show here."
    : S.domain === "clinical"
      ? "Every mark is one patient. Solid marks are the ones that model would enrol. " +
        "Both fields are the same admissions sorted by two different models, competing " +
        "for the same fixed number of places."
      : "Every mark is one person. Solid marks are the ones that approach would " +
        "contact. Pink marks are people who give less after being contacted than they " +
        "would have if left alone.");
  $("#fields").style.setProperty("--cols",
    isNarrow() ? 1 : (innerWidth > 1320 ? L.length : Math.min(2, L.length)));
  setHTML("#fields", L.map(s => `
    <div class="panel ${s.key === S.focus ? "active" : ""}" data-key="${s.key}"
         ${s.benchmark ? 'data-benchmark="true"' : ""}>
      <div class="panel-head">
        <h4><span class="panel-key" style="background:var(--${s.key})"></span>${s.label}</h4>
        <span class="q">${s.question}</span>
        ${s.benchmark
          ? `<span class="badge badge--benchmark">${COPY.trust.benchmark}</span>` : ""}
      </div>
      <canvas id="cv-${s.key}" aria-label="${s.label}: ${s.question}"></canvas>
      <div class="panel-meta">
        <span>contacting <b data-sel="${s.key}"></b></span>
        <span data-shared="${s.key}"></span>
        <span data-harmwrap="${s.key}"></span>
      </div>
    </div>`).join(""));
  S.fields.clear();
  L.forEach(s => {
    const cv = $("#cv-" + s.key);
    if (cv) S.fields.set(s.key, new Field(cv, { cols: isNarrow() ? 30 : 40 }));
  });
}

function renderFields({ animate = true } = {}) {
  if (!S.fields.size) renderPanels();
  const f = frame(), keys = listKeys();
  // Nothing is shown in place of a missing frame, and the rest of the page keeps
  // working. Painting from an absent frame would take the whole view down.
  if (!f || !Array.isArray(f.mask)) {
    setHTML("#fields", `<p class="sample-note">${COPY.states.domainMissing}</p>`);
    setHTML("#ribbonLegend", ""); setHTML("#fieldLegend", "");
    setText("#sampleNote", ""); setText("#ribbonLede", "");
    return;
  }
  // The first list is the reference every other field is read against. It is the
  // prediction the other rules are competing with, so it is the one that answers
  // "compared with what".
  const ref = lists()[0];
  const refIdx = keys.indexOf(dataKey(ref.key));
  lists().forEach(s => {
    const fl = S.fields.get(s.key); if (!fl) return;
    fl.setTargets(markColours(f, keys.indexOf(dataKey(s.key)), s.key,
      { referenceIndex: refIdx, referenceKey: ref.key }), { animate });
    requestAnimationFrame(() => fl.resize());
    const st = selectionStats(s.key);
    const a = $(`[data-sel="${s.key}"]`); if (a) a.textContent = fmt.int(st.sel);
    const sh = $(`[data-shared="${s.key}"]`);
    if (sh) sh.innerHTML = s.key === ref.key ? ""
      : `<b>${fmt.int(movement(ref.key, s.key).stayed)}</b> also on the first list`;
    const hw = $(`[data-harmwrap="${s.key}"]`);
    if (hw) hw.innerHTML = st.harmShare == null ? ""
      : `put off <b style="color:var(--harm)">${fmt.pct(st.harmShare)}</b>`;
  });

  setHTML("#fieldLegend",
    `<span><i style="background:var(--${ref.key})"></i>the first list</span>` +
    `<span><i style="background:var(--historical)"></i>kept by this rule</span>` +
    `<span><i style="background:${droppedTone(ref.key)}"></i>dropped by this rule</span>`);

  // Each institution compares its own two lists. The hospital's panel keys map
  // through clinicalKey(), and asking for "risk" and "effect" there resolved both
  // sides to the same underlying list, so the ribbon reported total agreement.
  const [a, b] =
    S.domain === "education" ? ["analyst_a", "analyst_b"] :
    S.domain === "clinical"  ? ["steadier", "accurate"]   : ["risk", "effect"];
  const mv = movement(a, b);
  const rib = $("#ribbon");
  if (rib) movementRibbon(rib, mv,
    S.domain === "education" ? ["--historical", "--analyst_a", "--analyst_b"] :
    S.domain === "clinical"  ? ["--historical", "--steadier", "--accurate"]   :
                               ["--historical", "--risk", "--effect"]);

  // The bar is the union of two lists. Naming what the grey band is before the
  // reader meets the counts is what makes shared against unique legible at all.
  const who = S.domain === "education" ? "analysts"
            : S.domain === "clinical" ? "models" : "rules";
  setText("#ribbonTitle", `Where the two ${who} agree`);
  setText("#ribbonLede",
    `Every person either ${who === "analysts" ? "analyst" : who.slice(0, -1)} would contact, ` +
    `in one bar. The grey band is the people chosen by both. The two coloured bands are ` +
    `the people only one of them chose.`);

  const chip = (v, n, label) =>
    `<span><i style="background:var(--${v})"></i><b>${fmt.int(n)}</b> ${label}</span>`;
  setHTML("#ribbonLegend",
    S.domain === "education"
      ? chip("historical", mv.stayed, "on both lists") +
        chip("analyst_a", mv.left, "only the first analyst") +
        chip("analyst_b", mv.entered, "only the second")
    : S.domain === "clinical"
      ? chip("historical", mv.stayed, "on both lists") +
        chip("steadier", mv.left, "only the steadier model") +
        chip("accurate", mv.entered, "only the more accurate model")
      : chip("historical", mv.stayed, "on both lists") +
        chip("risk", mv.left, "only the likely to give") +
        chip("effect", mv.entered, "only the ones a visit would change"));

  setText("#sampleNote", S.domain === "education"
    ? `${fmt.int(f.n_sampled)} students shown · the real list is ${fmt.int(f.k)} of ${fmt.int(f.n_eval)}`
    : `${fmt.int(f.n_sampled)} ${S.domain === "clinical" ? "patients" : "people"} shown · the real list is ${fmt.int(f.k)} of ${fmt.int(f.n_eval ?? S.roster.n_population)}`);
}

/* ---------- reveals ----------------------------------------------------- */

function renderReveals() {
  const f = () => frame();
  // Three tiers, always in the same order: what happened, the number, what it
  // means. A reader should never have to assemble the meaning themselves.
  const set = (id, claim, figure, note) => {
    const el = $(id); if (!el) return;
    el.innerHTML = `<span class="muted">${claim}</span>` +
      (figure ? `<em>${figure}</em>` : "") +
      (note ? `<span class="read">${note}</span>` : "");
  };

  if (S.domain === "education") {
    const floor = movement("analyst_a", "analyst_b");
    const div = movement("analyst_a", "effect");
    const d = S.edu.days[S.day];
    const first = S.edu.days[String(S.edu.decision_days[0])];
    set("#revealPeople",
      "Two analysts looked at the same students and disagreed about who to help.",
      `${fmt.pct(floor.jaccard)} agreement`,
      "Same method, same course, different halves of the record. Nothing separates them " +
      "but which students each one happened to learn from.");
    const last = S.edu.days[String(S.edu.decision_days.at(-1))];
    // This is one cohort. Across all cohorts, under honest transfer to a course the
    // model has not seen, the same gain is inside the noise. The page must not imply
    // the improvement is the finding when the analysis says the opposite.
    set("#revealOutcome",
      "Waiting made the model sharper and the list no more reproducible.",
      `${first.auc.toFixed(3)} \u2192 ${last.auc.toFixed(3)}`,
      "In this course, accuracy rises over twelve weeks. The two analysts still agree no " +
      "more than they did on day one, and by then more than half the students who left " +
      "have already gone.");
    set("#revealRep",
      "Sorting by who a conversation would change picks different students again.",
      `${fmt.pct(div.jaccard)} overlap`,
      "With the risk list. The two ways of choosing are not variations on each other.");
    const moved = S.day !== String(S.edu.decision_days[0]);
    setHTML("#readout", `
      <div><span class="stat-num">${fmt.pct(floor.jaccard)}</span>
        <span class="k">two analysts pick the same student</span></div>
      <div><span class="stat-num">${fmt.int(floor.stayed)}</span>
        <span class="k">students on both lists, of ${fmt.int(f().k)}</span></div>
      ${moved ? `<div><span class="stat-num">${(d.auc - first.auc >= 0 ? "+" : "") +
        (d.auc - first.auc).toFixed(3)}</span>
        <span class="k">the model sorts better than on day one</span></div>` : ""}
      <div><span class="stat-num" style="color:var(--effect)">${fmt.pct(div.jaccard)}</span>
        <span class="k">shared with the list a conversation would change</span></div>`);
    return;
  }

  if (S.domain === "clinical") {
    const c = frame();
    const churn = 1 - c.boosted.overlap_median, steady = 1 - c.logit.overlap_median;
    set("#revealPeople",
      "Rebuild the more accurate model and its list changes.",
      `${fmt.pct(c.boosted.overlap_median)} repeated`,
      `Rebuilt on a slightly different sample it keeps ${fmt.pct(c.boosted.overlap_median)} ` +
      `of its list. The slightly less accurate model keeps ${fmt.pct(c.logit.overlap_median)}.`);
    set("#revealOutcome",
      "Across eight rebuilds it named far more patients than the ward has beds.",
      `${c.boosted.union_over_k.toFixed(2)}\u00d7`,
      "Distinct patients named, per place available. Every one of them was, on some " +
      "rebuild, among those the model ranked most urgent.");
    set("#revealRep",
      "None of this shows up in the number the ward reports.",
      `${fmt.pct(c.boosted.reported_total_spread)}`,
      `That is how much the reported total moves between rebuilds, while ` +
      `${fmt.pct(churn)} of the people underneath it change.`);
    setHTML("#readout", `
      <div><span class="stat-num">${fmt.pct(c.boosted.overlap_median)}</span>
        <span class="k">the accurate model repeats between rebuilds</span></div>
      <div><span class="stat-num">${fmt.pct(c.logit.overlap_median)}</span>
        <span class="k">the steadier model repeats</span></div>
      <div><span class="stat-num harm-tone">${c.boosted.union_over_k.toFixed(2)}x</span>
        <span class="k">distinct patients named, per place available</span></div>
      <div><span class="stat-num">${fmt.pct(c.logit_vs_boosted)}</span>
        <span class="k">the two models agree on</span></div>`);
    return;
  }

  const mv = movement("risk", "effect");
  const cells = (S.adv.by_capacity || {})[S.cap] || {};
  const eq = (S.adv.equity || {}).observable || {};
  const d = eq.is_prior_donor ? eq.is_prior_donor["1"] : null;
  const R = COPY.reveals;
  const vars = {
    howDifferent: mv.jaccard < 0.15 ? "almost entirely different"
                : mv.jaccard < 0.5  ? "mostly different" : "partly different",
    jaccard: fmt.pct(mv.jaccard),
    effect: fmt.signed(cells.effect?.expected_incremental),
    risk: fmt.signed(cells.risk?.expected_incremental),
    hist: d ? fmt.pct(d.historical) : "\u2014",
    oracle: d ? fmt.pct(d.oracle) : "\u2014"
  };
  for (const [id, key] of [["#revealPeople", "people"],
                           ["#revealOutcome", "outcome"],
                           ["#revealRep", "representation"]]) {
    const r = R[key];
    set(id, fmt.tmpl(r.claim, vars), fmt.tmpl(r.figure, vars),
        fmt.tmpl(r.figureNote, vars) + ". " + r.read);
  }
  const rk = selectionStats("risk"), ef = selectionStats("effect");
  setHTML("#readout", `
    <div><span class="stat-num">${fmt.pct(mv.jaccard)}</span>
      <span class="k">of the two lists are the same people</span></div>
    <div><span class="stat-num harm-tone">${fmt.pct(rk.harmShare)}</span>
      <span class="k">of the likely list are put off by contact</span></div>
    <div><span class="stat-num harm-tone">${fmt.pct(ef.harmShare)}</span>
      <span class="k">of the list a visit would change are</span></div>
    <div><span class="stat-num" style="color:var(--oracle)">0.0%</span>
      <span class="k">of a perfect list would be</span></div>`);
}

/* ---------- table ------------------------------------------------------- */

function renderTable() {
  const head = $("#alloc thead tr"), body = $("#alloc tbody");
  const label = (t) => t.replace(/"/g, "&quot;");
  if (S.domain === "education") {
    head.innerHTML = `<th>Point in the term</th><th>Students seen</th>
      <th>How well it sorts</th><th>Two analysts agree</th><th>Shared with the conversation list</th>`;
    body.innerHTML = S.edu.decision_days.map(day => {
      const d = S.edu.days[String(day)], c = d.capacities[S.eduCap];
      const now = String(day) === S.day;
      return `<tr${now ? ' data-emphasis="true"' : ""}>
        <td data-label="Point">${day === 0 ? "Day one" : "Week " + Math.round(day / 7)}</td>
        <td class="n" data-label="Students seen">${fmt.int(c.n_eval)}</td>
        <td class="n${now ? " lead" : ""}" data-label="How well it sorts">${d.auc.toFixed(3)}</td>
        <td class="n" data-label="Two analysts agree">${fmt.pct(c.noise_floor)}</td>
        <td class="n" data-label="Shared with the conversation list">${fmt.pct(c.risk_vs_effect)}</td></tr>`;
    }).join("");
    setText("#tableTitle", "What changes as the term goes on");
    $("#tableLede").textContent =
      "The model sorts students better the longer it waits. Two analysts using that " +
      "better model still barely agree on who to contact.";
    return;
  }
  if (S.domain === "clinical") {
    head.innerHTML = `<th>Places available</th><th>Patients enrolled</th>
      <th>Steadier model repeats</th><th>Accurate model repeats</th>
      <th>Distinct patients named</th><th>Reported total moves</th>`;
    body.innerHTML = S.clin.capacities.map(cap => {
      const c = S.clin.by_capacity[cap.toFixed ? cap.toFixed(2) : cap];
      if (!c) return "";
      const now = (cap.toFixed ? cap.toFixed(2) : cap) === S.clinCap;
      return `<tr${now ? ' data-emphasis="true"' : ""}>
        <td data-label="Places available">${(cap * 100).toFixed(0)}%</td>
        <td class="n" data-label="Patients enrolled">${fmt.int(c.k)}</td>
        <td class="n" data-label="Steadier model repeats">${fmt.pct(c.logit.overlap_median)}</td>
        <td class="n${now ? " lead" : ""}" data-label="Accurate model repeats">${fmt.pct(c.boosted.overlap_median)}</td>
        <td class="n" data-label="Distinct patients named">${c.boosted.union_over_k.toFixed(2)}\u00d7</td>
        <td class="n" data-label="Reported total moves">${fmt.pct(c.boosted.reported_total_spread)}</td></tr>`;
    }).join("");
    setText("#tableTitle", "Accuracy against a decision you can repeat");
    setText("#tableLede",
      "The more accurate model sorts patients better, and its list changes when it is " +
      "rebuilt. Under a fixed number of places, the question is not which model scores " +
      "higher but which one produces a decision the ward can act on.");
    return;
  }
  head.innerHTML = `<th>Approach</th><th>Extra gifts caused</th><th>Share of what was possible</th>
    <th>Put off by contact</th><th>Already donors</th>`;
  const cells = (S.adv.by_capacity || {})[S.cap] || {};
  const eq = (S.adv.equity || {}).observable || {};
  const d = eq.is_prior_donor ? eq.is_prior_donor["1"] : null;
  body.innerHTML = STRATEGIES.filter(s => cells[s.key]).map(s => {
    const c = cells[s.key];
    return `<tr${s.benchmark ? ' data-emphasis="true"' : ""}>
      <td data-label="Approach">${s.label}${s.benchmark
        ? ' <span class="badge badge--benchmark">not achievable</span>' : ""}</td>
      <td class="n lead" data-label="Extra gifts caused">${fmt.signed(c.expected_incremental)}</td>
      <td class="n" data-label="Share of what was possible">${fmt.pct(c.effect_captured)}</td>
      <td class="n" data-label="Put off by contact">${fmt.pct(c.harm_share)}</td>
      <td class="n" data-label="Already donors">${d ? fmt.pct(d[s.key]) : "\u2014"}</td></tr>`;
  }).join("");
  setText("#tableTitle", "What each approach actually achieved");
  setText("#tableLede",
    "Because this population is invented, we know what each person would have done both " +
    "with a visit and without one. So each approach can be graded on the gifts it caused.");
}

/* ---------- chapters, method, footer ------------------------------------ */

// The fundraising chapter is the only one whose numbers are invented, so it carries an
// explicit ledger of what came from the analysis and what was chosen. It renders only
// for that institution; the other two have no such distinction to draw.
// The hero anchor is the finding itself: the same sampled people, sorted two ways,
// with the few who appear on both lists marked. Nothing decorative, and nothing that
// is not already in the export.
function renderHero() {
  const cv = $("#heroField");
  if (!cv || !S.roster) return;
  // The hero states the headline scenario. It does not follow the capacity control,
  // so the lede beside it stays true whatever the reader has selected below.
  const hk = (S.roster.headline_capacity ?? 0.03).toFixed(2);
  const f = S.roster.by_capacity[hk] || S.roster.by_capacity[S.cap];
  const keys = S.roster.strategies;
  const ir = keys.indexOf("risk"), ie = keys.indexOf("effect");
  const n = f.mask.length;
  const w = cv.clientWidth; if (!w) return;

  const dpr = Math.min(devicePixelRatio || 1, 2);
  // A mark below about six pixels stops reading as a person, so the field
  // gets coarser on a phone rather than simply smaller.
  const cols = isNarrow() ? 32 : 60;
  const rows = Math.ceil(n / cols), cell = w / cols;
  cv.width = Math.round(w * dpr);
  cv.height = Math.round(rows * cell * dpr);
  cv.style.height = rows * cell + "px";
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = css("--bg-1");
  g.fillRect(0, 0, w, rows * cell);

  let both = 0;
  const gap = cell > 7 ? 1 : 0;
  for (let i = 0; i < n; i++) {
    const r = ((f.mask[i] >> ir) & 1) === 1, e = ((f.mask[i] >> ie) & 1) === 1;
    if (r && e) both++;
    g.fillStyle = r && e ? css("--harm") : r ? css("--risk")
      : e ? css("--effect") : css("--unselected-ink");
    g.fillRect((i % cols) * cell, ((i / cols) | 0) * cell, cell - gap, cell - gap);
  }
  setHTML("#heroLegend", `
    <span><i style="background:var(--risk)"></i>chosen as most likely to give</span>
    <span><i style="background:var(--effect)"></i>chosen as who a visit would change</span>
    <span><i style="background:var(--harm)"></i>on both lists</span>`);
  setText("#heroCaption",
    `${fmt.int(f.n_sampled)} people from a fundraising office, sorted two defensible ` +
    `ways at the same capacity. ${fmt.int(both)} appear on both lists.`);
}

function renderEvidence() {
  const host = $("#evidenceLedger");
  if (!host) return;
  if (S.domain !== "advancement") { host.innerHTML = ""; return; }
  const rows = FUNDRAISING_EVIDENCE.map(e => {
    const meta = EVIDENCE[e.k] || {};
    return `<tr>
      <td><span class="badge badge--${e.k === "sourced" ? "analysis"
        : e.k === "invented" ? "invented" : "chosen"}"
        tabindex="0" data-tip="${(meta.tip || "").replace(/"/g, "&quot;")}">${meta.label}</span></td>
      <td><strong>${e.what}</strong><br>
        <span style="color:var(--dim);font-size:.88em">${e.detail}</span></td></tr>`;
  }).join("");
  host.innerHTML = `
    <div class="ed" style="margin-bottom:var(--step)">
      <div class="ed-lead">
        <span class="eyebrow">What is measured and what is chosen</span>
        <h3 style="margin-top:var(--s4);max-width:24ch">This institution is invented.
          Here is exactly which parts.</h3>
      </div>
      <div class="ed-side ed-side--base">
        <p style="color:var(--dim)">The other two institutions use real records. This one
        does not, and that is the point: it is the only place where the right answer can be
        checked. But nothing here describes real donors, and no number below was taken from
        a published figure.</p>
      </div>
      <div class="ed-full" style="margin-top:0">
        <div class="table-wrap"><table class="ledger"><tbody>${rows}</tbody></table></div>
      </div>
    </div>`;
}

function renderChapters() {
  const html = Object.entries(S.data.domains).map(([k, dm]) => {
    const c = COPY.chapterCopy[k] || {};
    if (!dm.available) {
      return `<article class="chapter">
        <span class="chapter-n">${c.n || ""}</span><h3>${c.label || k}</h3>
        <p style="color:var(--dim);font-size:.88rem">${COPY.states.domainMissing}</p>
      </article>`;
    }
    const sim = dm.data_status === "simulated";
    return `<article class="chapter">
      <span class="chapter-n">${c.n || ""} · ${c.label || ""}</span>
      <h3>${c.what || ""}</h3>
      <p style="color:var(--dim);font-size:.86rem;margin-top:6px">The help on offer: ${c.action || ""}.</p>
      <p class="finding">${c.finding || ""}</p>
      <p style="color:var(--dim);font-size:.9rem">${c.body || ""}</p>
      <div class="status">
        <span class="badge ${sim ? "badge--sim" : ""}">${sim ? COPY.trust.simulated : COPY.trust.observed}</span>
        <span class="badge">${dm.ground_truth_available ? "we know who was helped" : "we cannot know who was helped"}</span>
        ${dm.interactive ? '<span class="badge">explorable above</span>' : ""}
      </div>
    </article>`;
  }).join("");
  setHTML("#chapters", html);
}

function renderMethod() {
  const m = S.data._meta || {};
  const mo = (S.adv && S.adv.model) || {};
  const pop = (S.adv && S.adv.population) || {};
  const bias = Math.abs(pop.true_ate) ? pop.confounding_bias / Math.abs(pop.true_ate) : null;
  const hc = S.clin?.by_capacity?.[(S.clin?.headline_capacity ?? 0.05).toFixed(2)] || {};

  // Question, one line answer, then the detail. A reader who stops at the answer
  // should still have the point.
  const rows = [
    ["Two people, same method, different answers",
     "Two models built on different parts of the same student record agreed on about a quarter of who to prioritise.",
     `Nothing separates those two models but which students each one happened to learn
      from. Any claim that one way of sorting beats another has to be larger than that
      gap before it means anything, and much of the range tested is not.`],
    ["Could anyone have known who benefits?",
     `The things a fundraising database records explain <b>${fmt.pct(mo.effect_recovery_ceiling?.r2, 1)}</b> of the difference between people.`,
     `That figure comes from checking the answer directly, which is possible only because
      that population is invented. No method can beat what the data contains, so it caps
      every approach shown on this page. The limit is the information, not the model.`],
    ["Why current practice looks better than it is",
     `Comparing visited against not visited overstates the value of a visit by about <b>${bias == null ? "\u2014" : fmt.pct(bias, 0)}</b>.`,
     `Officers visit people who were already likely to give, so the comparison credits the
      visit with gifts that would have happened anyway. That mistake is built into this
      population deliberately, because real records contain it.`],
    ["Did the models see the answer?",
     "No. Anything knowable only afterwards is removed before training.",
     `Removed by name, and each step checks it is gone before it runs. In the invented
      population that includes the true outcome under both conditions, which is the whole
      reason that population is useful.`],
    ["Would the same list come back tomorrow?",
     "Not exactly. Rebuilt on a slightly different sample, the more accurate hospital model keeps only part of its list.",
     `At a typical programme size it keeps
      <b>${fmt.pct(hc.boosted?.overlap_median)}</b> of its list, while the slightly less
      accurate model keeps <b>${fmt.pct(hc.logit?.overlap_median)}</b>. The reported total
      barely moves in either case, so nothing in a standard report would reveal it.`],
    ["What is assumed rather than measured",
     "How much anyone benefits, in all three settings.",
     `Neither the university nor the hospital ran an experiment, so benefit is assumed
      there and varied across a wide range. The fundraising population is invented
      outright, and none of its numbers comes from a published figure.`],
    ["What would change the conclusion",
     "Evidence that outreach cannot make anyone worse off.",
     `The advantage of choosing on effect rather than on likelihood comes almost entirely
      from avoiding people the contact would put off. Where that group is absent, the two
      approaches are close and the simpler one wins. Where it is one in five, the gap
      becomes very large. That is the question to answer before switching.`]
  ];

  const html = rows.map(([q, answer, detail], i) => `
    <details class="method" ${i === 0 ? "open" : ""}>
      <summary>
        <span class="q-row"><span>${q}</span></span>
        <span class="answer">${answer}</span>
      </summary>
      <div class="inner">${detail}</div>
    </details>`).join("");
  setHTML("#methodList", html);
}

// Both real datasets carry attribution as a condition of use: OULAD is licensed
// CC BY 4.0, and PhysioNet asks every user of MIMIC-IV to cite the dataset, the
// paper describing it, and PhysioNet itself. The citations are reproduced as the
// providers give them; the full records live in the sources register.
function renderFooter() {
  const link = (href, text) =>
    `<a href="${href}" target="_blank" rel="noopener" style="color:inherit;` +
    `text-decoration:underline;text-decoration-color:var(--line-strong);` +
    `text-underline-offset:2px">${text}</a>`;
  const cite = html =>
    `<span style="display:block;margin-top:var(--s3);color:var(--text-faint);` +
    `font-size:.86em;line-height:1.55">${html}</span>`;
  const pop = S.roster?.n_population;

  setHTML("#foot", `
    <div class="cols">
      <div>
        <span class="eyebrow">Where the numbers come from</span>
        <p><strong>${COPY.provenance.headline}</strong></p>
        <p>${COPY.provenance.body}</p>
      </div>
      <div>
        <span class="eyebrow">The three sources</span>
        <p><strong>University.</strong> The Open University Learning Analytics Dataset:
        anonymised records from a UK distance learning university.
        ${cite(`Kuzilek J., Hlosta M., Zdrahal Z. Open University Learning Analytics
          dataset. Sci. Data 4:170171 (2017).
          ${link("https://doi.org/10.1038/sdata.2017.171", "doi:10.1038/sdata.2017.171")}.
          Licensed ${link("https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0")};
          the university figures on this page are derived from it.`)}</p>
        <p><strong>Hospital.</strong> MIMIC-IV, version 3.1: de-identified admission
        records from a US teaching hospital, used under a PhysioNet credentialed data use
        agreement. For a random sample of admissions, this page shows only which ones each
        model selected: no identifiers, no clinical values, no outcomes.
        ${cite(`Johnson A. et al. MIMIC-IV (version 3.1). PhysioNet (2024).
          ${link("https://doi.org/10.13026/kpb9-mt58", "doi:10.13026/kpb9-mt58")}.
          Johnson A.E.W. et al. MIMIC-IV, a freely accessible electronic health record
          dataset. Sci Data 10, 1 (2023).
          ${link("https://doi.org/10.1038/s41597-022-01899-x", "doi:10.1038/s41597-022-01899-x")}.
          Pollard T. et al. PhysioNet as a global platform for biomedical research.
          Nature Health (2026).
          ${link("https://doi.org/10.1038/s44360-026-00096-z", "doi:10.1038/s44360-026-00096-z")}.`)}</p>
        <p><strong>Fundraising.</strong> An invented population${pop ? ` of
        ${fmt.int(pop)}` : ""}. No number in it comes from a published figure. Not real
        donors.</p>
      </div>
    </div>`);
}

/* ---------- scaffolding ------------------------------------------------- */

function wireReveals() {
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }), { threshold: .35 });
  $$(".reveal").forEach(el => io.observe(el));
}
function wireNav() {
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return;
    $$(".nav-links a").forEach(a =>
      a.setAttribute("aria-current", String(a.getAttribute("href") === "#" + e.target.id)));
  }), { threshold: .3, rootMargin: "-58px 0px -55% 0px" });
  // Method lives in a section and Sources in the footer; observing only
  // `section[id]` left both links permanently unlit.
  $$("section[id],header[id],footer[id]").forEach(s => io.observe(s));
}
let rt;
addEventListener("resize", () => {
  clearTimeout(rt);
  rt = setTimeout(() => {
    renderPanels(); renderFields({ animate: false }); renderHero();
  }, 150);
});
function fail(msg) {
  setHTML("#app", `<div class="narrow state">
    <span class="eyebrow">${COPY.states.errorTitle}</span>
    <h2>Nothing is shown in place of a missing number.</h2>
    <div class="error">${msg}</div></div>`);
}

fetch("data/marginal.json")
  .then(r => r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status)))
  .then(d => {
    S.data = d;
    S.adv = d.domains?.advancement;
    S.edu = d.domains?.education?.roster || null;
    S.clin = d.domains?.clinical?.roster || null;
    if (!S.adv?.available || !S.adv.roster?.by_capacity) return fail(COPY.states.errorBody);
    S.roster = S.adv.roster;
    S.cap = (S.roster.headline_capacity ?? 0.03).toFixed(2);
    if (!S.roster.by_capacity[S.cap]) S.cap = Object.keys(S.roster.by_capacity)[0];
    if (S.edu) {
      S.day = String(S.edu.decision_days[0]);
      S.eduCap = (S.edu.headline_capacity ?? 0.10).toFixed(2);
      if (!S.edu.days[S.day].capacities[S.eduCap])
        S.eduCap = Object.keys(S.edu.days[S.day].capacities)[0];
      S.domain = "education";
    }
    // The hospital needs the same treatment. Without it the first click on that
    // institution looks up by_capacity[null], and every field asks for a frame
    // that does not exist.
    if (S.clin?.by_capacity) {
      S.clinCap = (S.clin.headline_capacity ?? 0.05).toFixed(2);
      if (!S.clin.by_capacity[S.clinCap])
        S.clinCap = Object.keys(S.clin.by_capacity)[0];
    }
    S.focus = lists()[0].key;
    setText("#scarcity", fmt.tmpl(COPY.scarcity, {
      pop: fmt.int(S.roster.n_population),
      k: fmt.int(S.roster.by_capacity[S.cap].k)
    }));
    document.body.classList.remove("loading");
    renderDomainSwitch(); renderRail(); wireFocus(); renderPanels();
    renderFields({ animate: false }); renderReveals(); renderTable(); renderEvidence();
    renderHero();
    renderChapters(); renderMethod(); renderFooter(); wireReveals(); wireNav();
  })
  .catch(e => fail(COPY.states.errorBody +
    `<br><br><span class="mono">${e.message}</span>`));
