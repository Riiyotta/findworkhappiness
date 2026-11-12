// Per-section live-vs-clone parity harness (optional build-time tool; verify_all.py never needs a browser).
//
// For every section in section-selectors.mjs it follows the SAME in-app path on both sides
// (load "/", wait, click the site's own "Enter without sound" gate, then $nuxt.$router.push to each
// route; deep routes 301 to "/" on a direct load on both hosts), brings each section instance into
// the viewport with the same wheel algorithm, waits the same settle times, crops the section's own
// bounding box (clipped to the viewport) and compares the two crops pixel by pixel.
//
// similarity = 1 - (pixels whose luminance differs by > 30) / (pixels compared)
// Gate: every captured section >= 0.80. The whole journey runs RUNS times (default 2) and the
// run-to-run agreement (max |delta| per section) is recorded; a harness whose scores disagree by
// more than 0.02 between runs is reported as unstable.
//
// Usage (machine paths only from the environment):
//   LIVE_URL=https://www.findworkhappiness.com BASE_URL=http://localhost:4173 \
//   PLAYWRIGHT_MODULE=$(npm root -g)/playwright node extraction/parity.mjs
// Output: extraction/evidence/parity-results.json (numbers and geometry only: no screenshots, no copy).
import { createRequire } from 'module';
import { writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { SECTION_SELECTORS } from './section-selectors.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const LIVE = (process.env.LIVE_URL || 'https://www.findworkhappiness.com').replace(/\/$/, '');
const BASE = (process.env.BASE_URL || 'http://localhost:4173').replace(/\/$/, '');
const RUNS = +(process.env.RUNS || 2);
const GATE = 0.8;
const AGREEMENT_TOLERANCE = 0.02;
const LUMA_THRESHOLD = 30;
const VIEWPORT = { width: 1440, height: 900 };
const APP_ROUTES = ['/', '/explore', '/chapter/one', '/navigation', '/about'];
const SETTLE = { firstLoad: 10000, afterGate: 5000, afterRoute: 6000, afterWheel: 1500, beforeCapture: 2500 };

async function bringIntoView(page, sel, idx, flow) {
  // The site's virtual scroller moves a fixed ~45px per wheel EVENT whatever the delta, so a single
  // large wheel barely moves it: send many small events, re-measure, then let the inertia settle.
  if (!flow) return;
  const topOf = () => page.evaluate(({ sel, idx }) => {
    const els = [...document.querySelectorAll(sel)].filter((e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; });
    return els[idx] ? els[idx].getBoundingClientRect().top : null;
  }, { sel, idx });
  // Stops early when the scroller reaches its end (a section near the page bottom can never reach
  // the top quarter): without this, end-of-page sections burned 4x400 wheel events each and a
  // two-run journey took over an hour. Applied identically on both sides.
  for (let pass = 0; pass < 4; pass++) {
    let top = await topOf();
    if (top === null || (top >= 0 && top < VIEWPORT.height * 0.25)) return;
    let prev = top; let stuck = 0; let atEnd = false;
    for (let i = 0; i < 400; i++) {
      await page.mouse.wheel(0, top > 100 ? 100 : -100);
      await page.waitForTimeout(25);
      if (i % 10 === 9) {
        top = await topOf();
        if (top === null || (top >= 0 && top < VIEWPORT.height * 0.25)) break;
        stuck = Math.abs(top - prev) < 2 ? stuck + 1 : 0; prev = top;
        if (stuck >= 3) { atEnd = true; break; }
      }
    }
    await page.waitForTimeout(SETTLE.afterWheel);
    if (atEnd) return;
  }
}

async function cropsFor(page, route) {
  const out = {};
  for (const [id, m] of Object.entries(SECTION_SELECTORS)) {
    if (!m.selector || !m.routes.includes(route)) continue;
    const n = await page.evaluate((sel) => [...document.querySelectorAll(sel)].filter((e) => {
      const s = getComputedStyle(e); const b = e.getBoundingClientRect();
      return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0 && b.width > 0 && b.height > 0;
    }).length, m.selector);
    const count = m.all ? n : Math.min(n, 1);
    for (let i = 0; i < count; i++) {
      await bringIntoView(page, m.selector, i, m.flow);
      await page.waitForTimeout(SETTLE.beforeCapture);
      const r = await page.evaluate(({ sel, idx, vw, vh }) => {
        const els = [...document.querySelectorAll(sel)].filter((e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; });
        const b = els[idx] && els[idx].getBoundingClientRect();
        if (!b) return null;
        const x = Math.max(0, b.left), y = Math.max(0, b.top);
        return { x, y, width: Math.min(vw, b.right) - x, height: Math.min(vh, b.bottom) - y, fullHeight: b.height };
      }, { sel: m.selector, idx: i, vw: VIEWPORT.width, vh: VIEWPORT.height });
      const key = `${route}|${id}|${i}`;
      if (!r || r.width < 4 || r.height < 4) { out[key] = { missing: true }; continue; }
      const clip = { x: Math.floor(r.x), y: Math.floor(r.y), width: Math.floor(r.width), height: Math.floor(r.height) };
      // capture with a 2px vertical margin so compare() can align both sides on their own
      // DOM-measured top edge (the momentum scroller can settle sub-pixel apart: see compare())
      const y0 = Math.max(0, clip.y - 2); const y1 = Math.min(VIEWPORT.height, clip.y + clip.height + 2);
      const png = await page.screenshot({ clip: { x: clip.x, y: y0, width: clip.width, height: y1 - y0 } });
      out[key] = { clip, marginTop: clip.y - y0, fullHeight: Math.round(r.fullHeight), png: png.toString('base64') };
    }
  }
  return out;
}

async function journey(origin) {
  // fresh browser per journey: several WebGL journeys in one browser exhausted the renderer
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--ignore-gpu-blocklist'] });
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  const page = await ctx.newPage();
  await page.goto(origin + '/', { waitUntil: 'networkidle', timeout: 120000 });
  await page.mouse.move(VIEWPORT.width / 2, VIEWPORT.height / 2);
  await page.waitForTimeout(SETTLE.firstLoad);
  const crops = {};
  Object.assign(crops, await cropsFor(page, '/'));
  // the site's own sound gate (normal entry flow, not a consent banner), clicked identically on both sides
  await page.locator('button.btn-no-sound').first().click({ force: true });
  await page.waitForTimeout(SETTLE.afterGate);
  for (const route of APP_ROUTES.slice(1)) {
    await page.evaluate((x) => window.$nuxt.$router.push(x), route);
    await page.waitForTimeout(SETTLE.afterRoute);
    Object.assign(crops, await cropsFor(page, route));
  }
  await page.goto(origin + '/formats/', { waitUntil: 'networkidle', timeout: 120000 });
  await page.waitForTimeout(SETTLE.beforeCapture);
  Object.assign(crops, await cropsFor(page, '/formats/'));
  await ctx.close();
  await browser.close();
  return crops;
}

// Compares the section crops of both sides, each aligned on its OWN DOM-measured top edge
// (crop rows start at marginTop). The site's momentum scroller can settle a sub-pixel apart on the
// two sides, so one side's floored top lands 1px above the other's; comparing raw viewport rows then
// shifts text by 1px and scored a matching chapter body 0.867 in one run and 1.0 in the next.
// The offset is MEASURED from the DOM on each side, never searched for, so a real layout shift
// still shows up as a difference in liveClip/cloneClip (both recorded in the results).
// Limit (measured 2026-11-12): alignment removes WHOLE-pixel offsets only. When the two scrollers
// settle a fraction of a pixel apart (chapter one body: floored tops 120 vs 121 in both runs), text
// rasterises differently and the section scores ~0.867 on every run; the same section scores 1.0
// when both sides land on the same offset. Reported as-is in README 'Parity', never masked.
async function compare(browser, L, C) {
  const page = await browser.newPage();
  const res = await page.evaluate(async ({ a, b, ma, mb, w, h, t }) => {
    const load = (s) => new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = 'data:image/png;base64,' + s; });
    const [ia, ib] = await Promise.all([load(a), load(b)]);
    const px = (img) => { const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const x = c.getContext('2d'); x.drawImage(img, 0, 0); return x.getImageData(0, 0, img.width, img.height).data; };
    const da = px(ia), db = px(ib);
    const rows = Math.min(h, ia.height - ma, ib.height - mb);
    let diff = 0;
    for (let y = 0; y < rows; y++) for (let x = 0; x < w; x++) {
      const i = ((y + ma) * ia.width + x) * 4, j = ((y + mb) * ib.width + x) * 4;
      const la = 0.299 * da[i] + 0.587 * da[i + 1] + 0.114 * da[i + 2];
      const lb = 0.299 * db[j] + 0.587 * db[j + 1] + 0.114 * db[j + 2];
      if (Math.abs(la - lb) > t) diff++;
    }
    return { similarity: 1 - diff / (w * rows), pixels: w * rows };
  }, { a: L.png, b: C.png, ma: L.marginTop, mb: C.marginTop, w: Math.min(L.clip.width, C.clip.width), h: Math.min(L.clip.height, C.clip.height), t: LUMA_THRESHOLD });
  await page.close();
  return { ...res, sizeMismatch: L.clip.width !== C.clip.width || L.clip.height !== C.clip.height };
}

const browser = await chromium.launch({ args: ['--use-gl=angle', '--ignore-gpu-blocklist'] });
const runs = [];
for (let r = 0; r < RUNS; r++) {
  const live = await journey(LIVE);
  const clone = await journey(BASE);
  const sections = {};
  for (const key of Object.keys({ ...live, ...clone }).sort()) {
    const L = live[key], C = clone[key];
    if (!L || !C || L.missing || C.missing) { sections[key] = { captured: false, live: !!(L && !L.missing), clone: !!(C && !C.missing) }; continue; }
    const cmp = await compare(browser, L, C);
    sections[key] = { captured: true, similarity: +cmp.similarity.toFixed(4), pixels: cmp.pixels, liveClip: L.clip, cloneClip: C.clip, sizeMismatch: cmp.sizeMismatch };
  }
  runs.push({ run: r + 1, sections });
  console.log('run', r + 1, 'done:', Object.keys(sections).length, 'section instances,', Object.values(sections).filter((x) => x.captured).length, 'captured');
}
await browser.close();

const keys = [...new Set(runs.flatMap((r) => Object.keys(r.sections)))].sort();
const summary = {};
for (const k of keys) {
  const scores = runs.map((r) => r.sections[k] && r.sections[k].captured ? r.sections[k].similarity : null);
  const got = scores.filter((s) => s !== null);
  summary[k] = {
    scores, min: got.length ? Math.min(...got) : null,
    runToRunMaxDelta: got.length > 1 ? +(Math.max(...got) - Math.min(...got)).toFixed(4) : null,
    passesGate: got.length === runs.length ? Math.min(...got) >= GATE : null,
  };
}
const captured = Object.values(summary).filter((s) => s.min !== null);
const out = {
  tool: 'extraction/parity.mjs',
  method: `per-section crop of each section's bounding box (clipped to the ${VIEWPORT.width}x${VIEWPORT.height} viewport) on both sides after the same in-app path and the same settle times; similarity = 1 - fraction of pixels whose luminance differs by > ${LUMA_THRESHOLD}, each side's crop aligned on its own DOM-measured top edge (2px capture margin; the measured offset is recorded as liveClip/cloneClip, never searched)`,
  live: LIVE, clone: BASE, viewport: VIEWPORT, settleMs: SETTLE, runs: RUNS,
  gate: GATE, agreementTolerance: AGREEMENT_TOLERANCE,
  captureState: 'sound gate clicked on both sides (site entry flow, not a consent banner); no cookie/consent banner exists on either side; mouse parked at viewport centre; nothing masked',
  capturedAt: new Date().toISOString().slice(0, 10),
  average: captured.length ? +(captured.reduce((a, s) => a + s.min, 0) / captured.length).toFixed(4) : null,
  allCapturedPassGate: captured.every((s) => s.passesGate === true),
  runsAgree: captured.every((s) => s.runToRunMaxDelta === null || s.runToRunMaxDelta <= AGREEMENT_TOLERANCE),
  sections: summary,
  perRun: runs,
};
writeFileSync(join(HERE, 'evidence', 'parity-results.json'), JSON.stringify(out, null, 1) + '\n');
console.log('average', out.average, 'allPass', out.allCapturedPassGate, 'runsAgree', out.runsAgree);
