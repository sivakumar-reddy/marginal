/* ==========================================================================
   MARGINAL — visualization
   One grammar, learned once:
     a mark is a person
     colour is the strategy that selected them
     magenta is harm
     dim is unselected
   Everything else in the product reuses this.
   ========================================================================== */

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const lerp = (a, b, t) => a + (b - a) * t;
const easeOut = t => 1 - Math.pow(1 - t, 3);

function hexToRgb(h) {
  h = (h || "").trim().replace("#", "");
  if (!/^[0-9a-fA-F]{3}$|^[0-9a-fA-F]{6}$/.test(h)) return [128, 128, 128];
  if (h.length === 3) h = h.split("").map(c => c + c).join("");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

/** Blend two hex colours. Used to sink a colour toward the unselected tone so a
    mark can say "this rule dropped them" without competing with a live selection. */
function mix(a, b, t) {
  const x = hexToRgb(a), y = hexToRgb(b);
  return "#" + [0, 1, 2]
    .map(i => Math.round(lerp(x[i], y[i], t)).toString(16).padStart(2, "0")).join("");
}

/**
 * A dense field of marks, one per sampled person.
 * Transitions are animated so the eye tracks who moved rather than
 * comparing two static pictures from memory.
 */
export class Field {
  constructor(canvas, opts = {}) {
    this.cv = canvas;
    this.g = canvas.getContext("2d", { alpha: false });
    this.cols = opts.cols || 40;
    this.reduced = matchMedia("(prefers-reduced-motion:reduce)").matches;
    this.state = null;      // per-mark rgb currently painted
    this.target = null;
    this.raf = null;
    this.bg = opts.bg || css("--bg-1") || "#0E1216";
  }

  /** colours: array of hex per mark */
  setTargets(colours, { animate = true } = {}) {
    const rgb = colours.map(hexToRgb);
    if (!this.state || this.state.length !== rgb.length || !animate || this.reduced) {
      this.state = rgb.map(c => c.slice());
      this.target = rgb;
      this.paint(1);
      return;
    }
    this.from = this.state.map(c => c.slice());
    this.target = rgb;
    this.t0 = performance.now();
    cancelAnimationFrame(this.raf);
    const tick = now => {
      const t = Math.min(1, (now - this.t0) / 420);
      const e = easeOut(t);
      for (let i = 0; i < this.state.length; i++)
        for (let k = 0; k < 3; k++)
          this.state[i][k] = lerp(this.from[i][k], this.target[i][k], e);
      this.paint(e);
      if (t < 1) this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  resize() {
    const w = this.cv.clientWidth;
    if (!w || !this.state) return;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const rows = Math.ceil(this.state.length / this.cols);
    const s = w / this.cols;
    this.cv.width = Math.round(w * dpr);
    this.cv.height = Math.round(rows * s * dpr);
    this.cv.style.height = rows * s + "px";
    this.dpr = dpr; this.s = s;
    this.paint(1);
  }

  paint() {
    if (!this.state) return;
    const { g, cv } = this;
    const dpr = this.dpr || Math.min(devicePixelRatio || 1, 2);
    const s = this.s || (cv.clientWidth / this.cols);
    if (!s) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = this.bg;
    g.fillRect(0, 0, cv.width / dpr, cv.height / dpr);
    const gap = s > 7 ? 1 : 0;
    for (let i = 0; i < this.state.length; i++) {
      const c = this.state[i];
      g.fillStyle = `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})`;
      g.fillRect((i % this.cols) * s, ((i / this.cols) | 0) * s, s - gap, s - gap);
    }
  }
}

/**
 * A slim horizontal ribbon showing who entered and who left when the
 * strategy changed. Answers "who moved" without a second dense field.
 */
export function movementRibbon(canvas, { entered, left, stayed },
                               vars = ["--historical", "--risk", "--effect"]) {
  const g = canvas.getContext("2d");
  const w = canvas.clientWidth, h = 34;
  if (!w) return;
  const dpr = Math.min(devicePixelRatio || 1, 2);
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.height = h + "px";
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  const total = entered + left + stayed || 1;
  const seg = [
    [stayed, css(vars[0])],
    [left, css(vars[1])],
    [entered, css(vars[2])]
  ];
  let x = 0;
  for (const [n, colour] of seg) {
    const pw = (n / total) * w;
    g.fillStyle = colour;
    g.fillRect(x, 0, Math.max(0, pw - 1), h);
    x += pw;
  }
}

/** The tone a mark takes when the reference list chose them and this rule did not.
    Exported so a legend can show the colour the field actually paints rather than
    an approximation of it. */
export function droppedTone(referenceKey) {
  return mix(css("--" + referenceKey) || css("--risk"),
             css("--unselected-ink"), .74);
}

/** Colour resolution shared by every field in the product. */
export function markColours(roster, strategyIndex, key,
                            { dim, referenceIndex = null, referenceKey = null } = {}) {
  // `harmed` is optional. Only some settings have an intervention that can leave a
  // person worse off; where none exists the channel is absent rather than all zero.
  const harmed = Array.isArray(roster.harmed) ? roster.harmed : null;
  const on = css("--" + key) || css("--risk");
  const harm = css("--harm");
  const off = dim || css("--unselected-ink");

  // A field read on its own says who a rule picked. Read against a reference it
  // says something the page is actually about: which people this rule keeps, which
  // it reaches for instead, and which it drops. Grey means both lists agree, the
  // same grey the movement ribbon uses, so the grammar is learned once.
  const comparing = referenceIndex != null && referenceIndex !== strategyIndex;
  const shared = css("--historical");
  const dropped = comparing
    ? mix(css("--" + (referenceKey || "risk")) || css("--risk"), off, .74)
    : off;

  const out = new Array(roster.mask.length);
  for (let i = 0; i < roster.mask.length; i++) {
    const sel = ((roster.mask[i] >> strategyIndex) & 1) === 1;
    const ref = comparing && ((roster.mask[i] >> referenceIndex) & 1) === 1;
    if (sel) out[i] = harmed && harmed[i] ? harm : (ref ? shared : on);
    else out[i] = ref ? dropped : off;
  }
  return out;
}
