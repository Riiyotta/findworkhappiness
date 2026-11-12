// Re-measure tool (optional; verify_all.py never needs a browser).
// Drives the running clone through in-app navigation (deep routes 301 to "/" on a
// direct load, exactly like the original host) and records, per viewport:
//   - computed-style histograms of visible elements (colour, type, radius, shadow)
//   - per-section geometry for every section contract (selector map below)
//   - visible copy per section (used to derive generated-mode leakage patterns)
//
// Usage (paths come from the environment, never hardcoded):
//   BASE_URL=http://localhost:4173 PLAYWRIGHT_MODULE=playwright node extraction/measure_sections.mjs
// PLAYWRIGHT_MODULE may be a package name or an absolute path to a playwright install.
// Output: extraction/evidence/computed-<width>.json
import { createRequire } from 'module';
import { writeFileSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE_URL || 'http://localhost:4173';
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 768, height: 1024 },
  { width: 390, height: 844, isMobile: true, hasTouch: true },
];

// section contract id -> selector map lives in section-selectors.mjs (shared with parity.mjs)
import { SECTION_SELECTORS } from './section-selectors.mjs';
export { SECTION_SELECTORS };

async function measurePage(page, route) {
  return page.evaluate(({ route, map }) => {
    const vis = (e) => { const s = getComputedStyle(e); const b = e.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0 && b.width > 0 && b.height > 0; };
    const hist = {};
    const bump = (k, v) => { if (!v) return; (hist[k] ||= {}); hist[k][v] = (hist[k][v] || 0) + 1; };
    for (const e of document.body.querySelectorAll('*')) {
      if (['SCRIPT', 'STYLE'].includes(e.tagName) || !vis(e)) continue;
      const s = getComputedStyle(e);
      const hasText = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (hasText) {
        bump('color', s.color); bump('fontFamily', `${s.fontFamily}|${s.fontWeight}|${s.fontStyle}`);
        bump('fontSize', s.fontSize); bump('lineHeight', s.lineHeight); bump('letterSpacing', s.letterSpacing);
        bump('textTransform', s.textTransform);
      }
      if (s.backgroundColor !== 'rgba(0, 0, 0, 0)') bump('backgroundColor', s.backgroundColor);
      if (s.borderTopLeftRadius !== '0px') bump('borderRadius', s.borderTopLeftRadius);
      if (s.boxShadow !== 'none') bump('boxShadow', s.boxShadow);
    }
    const sections = {};
    for (const [id, m] of Object.entries(map)) {
      if (!m.selector || !m.routes.includes(route)) continue;
      const els = [...document.querySelectorAll(m.selector)].filter(vis);
      if (!els.length) continue;
      const pick = m.all ? els : [els[0]];
      sections[id] = pick.map((e) => {
        let el = e;
        if (m.group === 'chapterHeader') {
          // header = "Ch." label + numeral title + headline: union of the three boxes
          const boxes = [e.previousElementSibling, e, e.nextElementSibling].filter(Boolean).map((x) => x.getBoundingClientRect());
          const top = Math.min(...boxes.map((b) => b.top)); const bottom = Math.max(...boxes.map((b) => b.bottom));
          return { heightPx: Math.round(bottom - top), widthPx: Math.round(boxes[1].width), topPx: Math.round(top), text: [e.previousElementSibling, e, e.nextElementSibling].map((x) => x && x.innerText.trim()).filter(Boolean) };
        }
        const b = el.getBoundingClientRect();
        const wc = (t) => (t.trim().match(/\S+/g) || []).length;
        const vis2 = (x) => { const bb = x.getBoundingClientRect(); return bb.width > 0 && bb.height > 0; };
        const structure = {
          headings: [...el.querySelectorAll('h1,h2,h3,h4')].filter(vis2).map((h) => ({ tag: h.tagName.toLowerCase(), words: wc(h.innerText), text: h.innerText.replace(/\s+/g, ' ').trim().slice(0, 120) })),
          paragraphWords: [...el.querySelectorAll('p')].filter(vis2).map((x) => wc(x.innerText)),
          links: [...el.querySelectorAll('a,button')].filter(vis2).map((x) => ({ tag: x.tagName.toLowerCase(), words: wc(x.innerText) })),
          images: [...el.querySelectorAll('img,canvas,svg')].filter(vis2).length,
          totalWords: wc(el.innerText),
        };
        return { heightPx: Math.round(b.height), widthPx: Math.round(b.width), topPx: Math.round(b.top), position: getComputedStyle(el).position, text: el.innerText.replace(/\s+/g, ' ').trim().slice(0, 600), structure };
      });
    }
    // page height = tallest scroll content (the site scrolls a fixed, overflow-hidden wrapper by transform)
    const scrollers = [...document.querySelectorAll('div.fixed.inset-0.overflow-hidden > div')];
    const pageHeightPx = Math.max(window.innerHeight, ...scrollers.map((s) => Math.round(s.getBoundingClientRect().height)), document.documentElement.scrollHeight);
    return { route, rootFontSize: getComputedStyle(document.documentElement).fontSize, pageHeightPx, sections, hist };
  }, { route, map: SECTION_SELECTORS });
}

const ROUTES = ['/', '/explore', '/chapter/one', '/navigation', '/about'];
const browser = await chromium.launch({ args: ['--use-gl=angle', '--ignore-gpu-blocklist'] });
mkdirSync(join(HERE, 'evidence'), { recursive: true });
for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile, hasTouch: !!vp.hasTouch });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(10000);
  const pages = [await measurePage(page, '/')];
  await page.locator('button.btn-no-sound').first().click({ force: true });
  await page.waitForTimeout(5000);
  for (const r of ROUTES.slice(1)) {
    await page.evaluate((x) => window.$nuxt.$router.push(x), r);
    await page.waitForTimeout(6000);
    pages.push(await measurePage(page, r));
  }
  await page.goto(BASE + '/formats/', { waitUntil: 'networkidle' });
  pages.push(await measurePage(page, '/formats/'));
  const out = { capturedFrom: BASE, viewport: { width: vp.width, height: vp.height }, capture: 'in-app navigation from "/" after clicking the sound gate (button.btn-no-sound); 6s settle per route', pages };
  writeFileSync(join(HERE, 'evidence', `computed-${vp.width}.json`), JSON.stringify(out, null, 1) + '\n');
  console.log('wrote computed-' + vp.width + '.json');
  await ctx.close();
}
await browser.close();
