// Deterministic evidence extractor (optional build-time tool; verify_all.py never runs it).
// Reads the mirrored production build in ../site (sibling of design-repo/) and writes
// pretty-printed, line-citeable evidence files into extraction/evidence/:
//   site.css         server-rendered stylesheet from site/index.html, one declaration per line
//   embedded.css     component stylesheets embedded in the lazy JS chunks, one declaration per line
//   motion.txt       every GSAP ease/duration/CustomEase and CSS transition occurrence, with chunk + offset
//   markup.txt       render-function element fragments (tag + staticClass, 200 chars max) per chunk, one per line
//   copy.json        chapter registry (titles, headlines, paragraph/word counts), nav labels, outbound URLs
//   asset-inventory.json every mirrored media/asset file (path, bytes, sha256; no content) - grounds asset roles and leakage patterns
//   source-pins.json sha256 of every source file read, so drift in the source is detectable
// Usage: node extraction/extract_evidence.mjs [path-to-site-dir]   (default: ../site relative to design-repo)
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'fs';
import { createHash } from 'crypto';
import { dirname, join, relative } from 'path';
import { fileURLToPath } from 'url';
import vm from 'vm';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = dirname(HERE);
const SITE = process.argv[2] || join(REPO, '..', 'site');
if (!existsSync(join(SITE, 'index.html'))) { console.error('source site not found at', SITE); process.exit(2); }
const OUT = join(HERE, 'evidence');
const pins = {};
const read = (rel) => { const buf = readFileSync(join(SITE, rel)); pins['site/' + rel] = 'sha256:' + createHash('sha256').update(buf).digest('hex'); return buf.toString('utf8'); };

function pretty(css) {
  css = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const out = []; let ind = 0; let line = '';
  for (const t of css.split(/([{};])/)) {
    if (t === '{') { out.push('  '.repeat(ind) + line.trim() + ' {'); ind++; line = ''; }
    else if (t === ';') { if (line.trim()) out.push('  '.repeat(ind) + line.trim() + ';'); line = ''; }
    else if (t === '}') { if (line.trim()) out.push('  '.repeat(ind) + line.trim() + ';'); ind = Math.max(0, ind - 1); out.push('  '.repeat(ind) + '}'); line = ''; }
    else line += t;
  }
  return out.join('\n') + '\n';
}

// 1. SSR stylesheet
const html = read('index.html');
const ssr = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join('');
writeFileSync(join(OUT, 'site.css'), pretty(ssr));

// 2. chunk-embedded stylesheets + 3. motion excerpts
const chunks = readdirSync(join(SITE, '_nuxt')).filter((f) => f.endsWith('.js')).sort();
let embedded = '';
const motion = [];
for (const f of chunks) {
  const js = read('_nuxt/' + f);
  for (const m of js.matchAll(/\[[a-zA-Z]\.i,"((?:[^"\\]|\\.)*)",""\]/g)) embedded += `/* chunk ${f} */\n` + JSON.parse('"' + m[1] + '"') + '\n';
  const re = /CustomEase[^;]{0,40}?\.create\("[^"]+","[^"]+"\)|\.create\("(?:snappy|expo)[^)]*\)|ease:"[A-Za-z0-9.()-]+"|duration:[0-9.]+|stagger:[0-9.]+|delay:[0-9.]+/g;
  for (const m of js.matchAll(re)) motion.push(`${f}@${m.index}\t${m[0]}`);
}
writeFileSync(join(OUT, 'embedded.css'), pretty(embedded));
// 2b. markup fragments: split each chunk's compiled render functions at element-creation calls
const TAGS = 'div|section|article|header|footer|nav|h1|h2|h3|h4|p|a|button|canvas|img|span|figure|figcaption|ul|li|svg|main|client-only|NuxtLink|nuxt-link|picture|video|audio|strong';
const splitRe = new RegExp('(?=\\b[a-z]\\("(?:' + TAGS + ')"[,)])', 'g');
const markup = ['# one element fragment per line: <chunk>\\t<first 200 chars of the compiled createElement call>'];
for (const f of chunks) {
  const js = readFileSync(join(SITE, '_nuxt', f), 'utf8');
  for (const part of js.split(splitRe).slice(1)) if (/staticClass|_v\(/.test(part.slice(0, 300))) markup.push(f + '\t' + part.slice(0, 200).replace(/[\r\n\t]+/g, ' '));
}
writeFileSync(join(OUT, 'markup.txt'), markup.join('\n') + '\n');
const cssAll = ssr + embedded;
for (const m of cssAll.matchAll(/transition:[^;}]+|animation:[^;}]+|cubic-bezier\([^)]*\)/g)) motion.push(`css\t${m[0]}`);
writeFileSync(join(OUT, 'motion.txt'), '# one occurrence per line: <chunk>@<byte offset>\\t<token>  (css = stylesheet)\n' + motion.join('\n') + '\n');

// 4. copy registry from the static Nuxt payloads
const TS = readdirSync(join(SITE, '_nuxt', 'static'))[0];
const payload = (route) => {
  const src = read(`_nuxt/static/${TS}/${route ? route + '/' : ''}payload.js`);
  let data; vm.runInNewContext(src, { __NUXT_JSONP__: (_n, d) => { data = d; } });
  return data;
};
const words = (s) => (s.trim().match(/\S+/g) || []).length;
const textOf = (node) => (node.value || '') + (node.children || []).map(textOf).join('');
const chapters = [];
for (const slug of ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']) {
  const p = payload('chapter/' + slug).data[0].page;
  const paras = p.text.value.document.children.map(textOf);
  const marks = new Set(); JSON.stringify(p.text.value, (k, v) => { if (k === 'marks') v.forEach((x) => marks.add(x)); return v; });
  chapters.push({ slug, title: p.title, introTitle: p.introTitle, introTitleWords: words(p.introTitle), audioPlayerTitle: p.audioPlayerTitle,
    paragraphs: paras.length, bodyWords: paras.reduce((a, s) => a + words(s), 0), maxParagraphWords: Math.max(...paras.map(words)),
    marks: [...marks].sort(), audio: p.audio && p.audio.url, illustration: p.illustration && p.illustration.url });
}
const allJs = chunks.map((f) => readFileSync(join(SITE, '_nuxt', f), 'utf8')).join('\n');
const outbound = [...new Set([...allJs.matchAll(/href:"(https?:\/\/[^"]+)"/g)].map((m) => m[1]))].filter((u) => !u.includes('nuxtjs.org')).sort();
const formats = readFileSync(join(SITE, 'formats', 'index.html'), 'utf8');
pins['site/formats/index.html'] = 'sha256:' + createHash('sha256').update(formats).digest('hex');
const formatLinks = [...new Set([...formats.matchAll(/href="(https?:\/\/[^"]+)"/g)].map((m) => m[1]))].sort();
const copy = {
  site: { title: (html.match(/<title>([^<]*)<\/title>/) || [])[1], description: (html.match(/property="description" content="([^"]*)"/) || [])[1] },
  chapters,
  outboundUrls: outbound,
  formatsDownloadUrls: formatLinks,
};
writeFileSync(join(OUT, 'copy.json'), JSON.stringify(copy, null, 1) + '\n');
// 5. asset inventory (paths + sizes + hashes only)
const MEDIA = /\.(png|jpe?g|svg|webp|gif|mp3|mp4|riv|ktx2|gltf|glb|bin|woff2?|wasm|ico)$/i;
const inv = [];
const walkDir = (dir) => { for (const e of readdirSync(join(SITE, dir), { withFileTypes: true })) {
  const rel = dir ? dir + '/' + e.name : e.name;
  if (e.isDirectory()) { if (!['__graphql'].includes(rel)) walkDir(rel); }
  else if (MEDIA.test(e.name)) { const b = readFileSync(join(SITE, rel)); inv.push({ path: 'site/' + rel, bytes: b.length, sha256: createHash('sha256').update(b).digest('hex') }); }
} };
walkDir('');
inv.sort((a, b) => a.path.localeCompare(b.path));
writeFileSync(join(OUT, 'asset-inventory.json'), JSON.stringify({ note: 'mirrored media/asset files of the source (paths relative to the project root); reference evidence only, no file content', files: inv }, null, 1) + '\n');
writeFileSync(join(OUT, 'source-pins.json'), JSON.stringify({ note: 'sha256 of every mirrored source file extract_evidence.mjs read; paths relative to the project root (sibling of design-repo/)', staticPayloadDir: TS, pins }, null, 1) + '\n');
console.log('evidence written to', relative(process.cwd(), OUT), '-', chapters.length, 'chapters,', motion.length, 'motion tokens,', Object.keys(pins).length, 'pinned files');
