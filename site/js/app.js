/* ==========================================================================
   MARGINAL — application

   Two institutions are explorable. They ask the same question but the thing
   that varies is different in each, so the controls differ:

     university    a moment in the term. How much do you know yet?
     fundraising   nothing varies but the rule. Both know everything.

   The visual grammar does not change between them. A mark is a person, a
   colour is an approach, pink is harm, dim is not selected.
   ========================================================================== */

import { Field, markColours, movementRibbon } from "./viz.js";
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

const UNI_LISTS = [
  { key: "analyst_a", label: "One analyst's list", question: "Who looks most at risk?", short: "analyst" },
  { key: "analyst_b", label: "A second analyst", question: "Same method, other half of the history", short: "second" },
  { key: "effect", label: "Who could be changed", question: "Who would a conversation move?", short: "movable" }
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
  if (S.domain === "education") return S.edu.days[S.day].capacities[S.eduCap];
  if (S.domain === "clinical") return S.clin.by_capacity[S.clinCap];
  return S.roster.by_capacity[S.cap];
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
        ${pct % 1 ? pct.toFixed(1) : pct}%<span class="op">${op ? "a typical programme" : "&nbsp;"}</span></button>`;
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
        ${pct % 1 ? pct.toFixed(1) : pct}%<span class="op">${op ? "what they have" : "&nbsp;"}</span></button>`;
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
  setText("#exploreLede", S.domain === "education"
    ? "Every mark is one student. Solid marks are the ones that approach would contact. " +
      "Nobody is made worse off by a conversation, so there is no harm to show here."
    : "Every mark is one person. Solid marks are the ones that approach would contact. " +
      "Pink marks are people who give less after being contacted than they would have if " +
      "left alone.");
  $("#fields").style.setProperty("--cols",
    isNarrow() ? 1 : (innerWidth > 1320 ? L.length : Math.min(2, L.length)));
  setHTML("#fields", L.map(s => `
    <div class="panel ${s.key === S.focus ? "active" : ""}" data-key="${s.key}"
         ${s.benchmark ? 'data-benchmark="true"' : ""}>
      <div class="panel-head">
        <h4><span class="panel-key" style="background:var(--${s.key})"></span>${s.label}</h4>
        ${s.benchmark
          ? `<span class="badge badge--benchmark">${COPY.trust.benchmark}</span>`
          : `<span class="q">${s.question}</span>`}
      </div>
      <canvas id="cv-${s.key}" aria-label="${s.label}: ${s.question}"></canvas>
      <div class="panel-meta">
        <span>contacting <b data-sel="${s.key}"></b></span>
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
  lists().forEach(s => {
    const fl = S.fields.get(s.key); if (!fl) return;
    fl.setTargets(markColours(f, keys.indexOf(dataKey(s.key)), s.key), { animate });
    requestAnimationFrame(() => fl.resize());
    const st = selectionStats(s.key);
    const a = $(`[data-sel="${s.key}"]`); if (a) a.textContent = fmt.int(st.sel);
    const hw = $(`[data-harmwrap="${s.key}"]`);
    if (hw) hw.innerHTML = st.harmShare == null ? ""
      : `put off <b style="color:var(--harm)">${fmt.pct(st.harmShare)}</b>`;
  });

  const [a, b] = S.domain === "education" ? ["analyst_a", "analyst_b"] : ["risk", "effect"];
  const mv = movement(a, b);
  const rib = $("#ribbon");
  if (rib) movementRibbon(rib, mv, S.domain === "education"
    ? ["--historical", "--analyst_a", "--analyst_b"]
    : ["--historical", "--risk", "--effect"]);
  setHTML("#ribbonLegend", S.domain === "education"
    ? `<span style="color:var(--historical)">${fmt.int(mv.stayed)} chosen by both</span> ·
       <span style="color:var(--analyst_a)">${fmt.int(mv.left)} only the first analyst</span> ·
       <span style="color:var(--analyst_b)">${fmt.int(mv.entered)} only the second</span>`
    : `<span style="color:var(--historical)">${fmt.int(mv.stayed)} on both</span> ·
       <span style="color:var(--risk)">${fmt.int(mv.left)} only the likely</span> ·
       <span style="color:var(--effect)">${fmt.int(mv.entered)} only the movable</span>`);

  setText("#sampleNote", S.domain === "education"
    ? `${fmt.int(f.n_sampled)} students shown · the real list is ${fmt.int(f.k)} of ${fmt.int(f.n_eval)}`
    : `${fmt.int(f.n_sampled)} people shown · the real list is ${fmt.int(f.k)} of ${fmt.int(S.roster.n_population)}`);
}

/* ---------- reveals ----------------------------------------------------- */

function renderReveals() {
  const f = () => frame();
  const set = (id, pre, post) => {
    const el = $(id); if (!el) return;
    el.innerHTML = `<span class="muted">${pre}</span> <em>${post}</em>`;
  };

  if (S.domain === "education") {
    const floor = movement("analyst_a", "analyst_b");
    const div = movement("analyst_a", "effect");
    const d = S.edu.days[S.day];
    const first = S.edu.days[String(S.edu.decision_days[0])];
    set("#revealPeople", "Two analysts. Same method. Same students.",
      `Only ${fmt.pct(floor.jaccard)} of the same names.`);
    const last = S.edu.days[String(S.edu.decision_days.at(-1))];
    // This is one cohort. Across all cohorts, under honest transfer to a course the
    // model has not seen, the same gain is inside the noise. The page must not imply
    // the improvement is the finding when the analysis says the opposite.
    set("#revealOutcome",
      `In this course the model sorts better by week ${
        Math.round(S.edu.decision_days.at(-1) / 7)}, ` +
      `${first.auc.toFixed(3)} to ${last.auc.toFixed(3)}.`,
      `The two analysts agree no more than they did on day one.`);
    set("#revealRep", "Sorting by who could be changed instead:",
      `${fmt.pct(div.jaccard)} of the same students.`);
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
        <span class="k">shared with the list of who could be changed</span></div>`);
    return;
  }

  if (S.domain === "clinical") {
    const c = frame();
    const churn = 1 - c.boosted.overlap_median, steady = 1 - c.logit.overlap_median;
    set("#revealPeople", "Two models, same records.",
      `The accurate one repeats ${fmt.pct(c.boosted.overlap_median)} of its list. The steadier one, ${fmt.pct(c.logit.overlap_median)}.`);
    set("#revealOutcome", "Rebuild them and the accurate model names",
      `${c.boosted.union_over_k.toFixed(2)} wards' worth of different patients to fill one ward.`);
    set("#revealRep", "The number the ward reports barely moves.",
      `${fmt.pct(c.boosted.reported_total_spread)}, while the people move ${fmt.pct(churn)}.`);
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
  set("#revealPeople", COPY.reveals.people.pre,
    fmt.tmpl(COPY.reveals.people.post, { jaccard: fmt.pct(mv.jaccard) }));
  set("#revealOutcome", COPY.reveals.outcome.pre,
    fmt.tmpl(COPY.reveals.outcome.post, {
      effect: fmt.signed(cells.effect?.expected_incremental),
      risk: fmt.signed(cells.risk?.expected_incremental)
    }));
  set("#revealRep", COPY.reveals.representation.pre,
    fmt.tmpl(COPY.reveals.representation.post, {
      hist: d ? fmt.pct(d.historical) : "—", oracle: d ? fmt.pct(d.oracle) : "—"
    }));
  const rk = selectionStats("risk"), ef = selectionStats("effect");
  setHTML("#readout", `
    <div><span class="stat-num">${fmt.pct(mv.jaccard)}</span>
      <span class="k">of the two lists are the same people</span></div>
    <div><span class="stat-num harm-tone">${fmt.pct(rk.harmShare)}</span>
      <span class="k">of the likely list are put off by contact</span></div>
    <div><span class="stat-num harm-tone">${fmt.pct(ef.harmShare)}</span>
      <span class="k">of the movable list are</span></div>
    <div><span class="stat-num" style="color:var(--oracle)">0.0%</span>
      <span class="k">of a perfect list would be</span></div>`);
}

/* ---------- table ------------------------------------------------------- */

function renderTable() {
  const head = $("#alloc thead tr"), body = $("#alloc tbody");
  if (S.domain === "education") {
    head.innerHTML = `<th>Point in the term</th><th>Students seen</th>
      <th>How well it sorts</th><th>Two analysts agree</th><th>Overlap with movable</th>`;
    body.innerHTML = S.edu.decision_days.map(day => {
      const d = S.edu.days[String(day)], c = d.capacities[S.eduCap];
      return `<tr${String(day) === S.day ? ' style="color:var(--text)"' : ""}>
        <td>${day === 0 ? "Day one" : "Week " + Math.round(day / 7)}</td>
        <td class="n">${fmt.int(c.n_eval)}</td>
        <td class="n">${d.auc.toFixed(3)}</td>
        <td class="n">${fmt.pct(c.noise_floor)}</td>
        <td class="n">${fmt.pct(c.risk_vs_effect)}</td></tr>`;
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
      return `<tr${(cap.toFixed ? cap.toFixed(2) : cap) === S.clinCap
        ? ' style="color:var(--text)"' : ""}>
        <td>${(cap * 100).toFixed(0)}%</td>
        <td class="n">${fmt.int(c.k)}</td>
        <td class="n">${fmt.pct(c.logit.overlap_median)}</td>
        <td class="n">${fmt.pct(c.boosted.overlap_median)}</td>
        <td class="n">${c.boosted.union_over_k.toFixed(2)}x</td>
        <td class="n">${fmt.pct(c.boosted.reported_total_spread)}</td></tr>`;
    }).join("");
    setText("#tableTitle", "Accuracy against repeatability");
    setText("#tableLede",
      "The more accurate model wins every standard test and cannot produce the same " +
      "ward list twice. Nothing here depends on any assumption about who benefits.");
    return;
  }
  head.innerHTML = `<th>Approach</th><th>Extra gifts caused</th><th>Share of what was possible</th>
    <th>Put off by contact</th><th>Already donors</th>`;
  const cells = (S.adv.by_capacity || {})[S.cap] || {};
  const eq = (S.adv.equity || {}).observable || {};
  const d = eq.is_prior_donor ? eq.is_prior_donor["1"] : null;
  body.innerHTML = STRATEGIES.filter(s => cells[s.key]).map(s => {
    const c = cells[s.key];
    return `<tr><td>${s.label}${s.benchmark
      ? ' <span class="badge badge--benchmark">not achievable</span>' : ""}</td>
      <td class="n">${fmt.signed(c.expected_incremental)}</td>
      <td class="n">${fmt.pct(c.effect_captured)}</td>
      <td class="n">${fmt.pct(c.harm_share)}</td>
      <td class="n">${d ? fmt.pct(d[s.key]) : "—"}</td></tr>`;
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
function renderEvidence() {
  const host = $("#evidenceLedger");
  if (!host) return;
  if (S.domain !== "advancement") { host.innerHTML = ""; return; }
  const rows = FUNDRAISING_EVIDENCE.map(e => {
    const meta = EVIDENCE[e.k] || {};
    return `<tr>
      <td><span class="badge ${e.k === "illustrative" ? "badge--sim" : ""}">${meta.label}</span></td>
      <td><strong>${e.what}</strong><br>
        <span style="color:var(--dim);font-size:.88em">${e.detail}</span></td></tr>`;
  }).join("");
  host.innerHTML = `
    <span class="eyebrow" style="margin-top:var(--step);display:block">What is measured and what is chosen</span>
    <h3 style="margin-top:12px">This institution is invented. Here is exactly which parts.</h3>
    <p class="measure" style="color:var(--dim);margin-top:8px">
      The other two institutions use real records. This one does not, and that is the
      point: it is the only place where the right answer can be checked. But nothing here
      describes real donors, and no number below was taken from a published figure.</p>
    <table style="margin-top:16px"><tbody>${rows}</tbody></table>`;
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
  const rows = [
    ["Two people, same method, different answers",
     `At the university, two models built on different thirds of the same student history
      agree on only about a quarter of the names at the top. Nothing separates them but
      which students each one happened to learn from. Any claim that one way of sorting
      beats another has to be larger than that gap before it means anything.`],
    ["Could anyone have known who benefits?",
     `In the invented fundraising population, the things a database actually records explain
      only <b>${fmt.pct(mo.effect_recovery_ceiling && mo.effect_recovery_ceiling.r2, 1)}</b>
      of the difference between people. No method can beat what the data contains.`],
    ["Why current practice looks better than it is",
     `Officers visit people who were already likely to give, so comparing visited against
      not visited credits the visit with gifts that would have happened anyway. It
      overstates the value by about <b>${bias == null ? "\u2014" : fmt.pct(bias, 0)}</b>.
      That mistake is built in deliberately, because real records contain it.`],
    ["Did the models see the answer?",
     `No. Anything that could only be known afterwards is removed by name before training,
      and each step checks it is gone before it runs.`],
    ["Would the same list come back tomorrow?",
     `At the hospital, the more accurate model wins every standard test and cannot produce
      the same ward list twice. The steadier one gives up a little accuracy and returns
      nearly the same people. That trade is reported rather than buried.`],
    ["What is assumed rather than measured",
     `Neither the university nor the hospital ran an experiment, so how much anyone benefits
      is assumed there and varied across a wide range. The fundraising population is
      invented outright. None of its numbers are published figures.`],
    ["Can this be reproduced?",
     `Yes. Every figure traces to the step that produced it and the whole analysis reruns to
      the same numbers from a fixed starting point.${m.git_commit
        ? ` This page was built from version <b>${m.git_commit}</b>.` : ""}`]
  ];
  const html = rows.map(([q, body], i) => `
    <details class="method" ${i === 0 ? "open" : ""}>
      <summary>${q}</summary><div class="inner measure">${body}</div>
    </details>`).join("");
  setHTML("#method", html);
}

function renderFooter() {
  const m = S.data._meta || {};
  const gaps = (S.data._gaps && S.data._gaps.length)
    ? S.data._gaps.length + " figure(s) missing and left blank"
    : "no missing figures";
  setHTML("#foot", `
    <div class="cols">
      <div><span class="eyebrow">Where the numbers come from</span>
        <p><strong>${COPY.provenance.headline}</strong></p>
        <p>${COPY.provenance.body}</p></div>
      <div><span class="eyebrow">The three sources</span>
        <p>University: anonymised student records from a distance learning university.<br>
        Hospital: de-identified admission records from a US teaching hospital, used under a
        credentialed research agreement.<br>
        Fundraising: an invented population. Not real donors.</p></div>
      <div><span class="eyebrow">This build</span>
        <p class="mono">${(m.generated_at || "").slice(0, 10)}${
          m.git_commit ? " \u00b7 " + m.git_commit : ""}<br>${gaps}</p></div>
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
  $$("section[id]").forEach(s => io.observe(s));
}
let rt;
addEventListener("resize", () => {
  clearTimeout(rt);
  rt = setTimeout(() => { renderPanels(); renderFields({ animate: false }); }, 150);
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
    S.focus = lists()[0].key;
    setText("#scarcity", fmt.tmpl(COPY.scarcity, {
      pop: fmt.int(S.roster.n_population),
      k: fmt.int(S.roster.by_capacity[S.cap].k)
    }));
    document.body.classList.remove("loading");
    renderDomainSwitch(); renderRail(); wireFocus(); renderPanels();
    renderFields({ animate: false }); renderReveals(); renderTable(); renderEvidence();
    renderChapters(); renderMethod(); renderFooter(); wireReveals(); wireNav();
  })
  .catch(e => fail(COPY.states.errorBody +
    `<br><br><span class="mono">${e.message}</span>`));
