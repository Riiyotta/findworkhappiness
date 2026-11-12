// Local mirror server for the findworkhappiness.com clone.
// - Serves ./site as static files (with HTTP Range support for audio scrubbing)
// - Maps Nuxt routes (/about, /chapter/one, ...) to their generated index.html
// - Answers the DatoCMS GraphQL calls from ./site/__graphql/cache (offline);
//   on a cache miss it proxies to DatoCMS once and stores the response.
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.join(__dirname, 'site');
const CACHE = path.join(ROOT, '__graphql', 'cache');
const PORT = Number(process.env.PORT) || 4173;
const DATO_TOKEN = '311e2c2208965da2722993191ec4a3'; // public read-only token shipped in the original bundle

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.otf': 'font/otf',
  '.mp3': 'audio/mpeg', '.mp4': 'video/mp4', '.wasm': 'application/wasm',
  '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream', '.ktx2': 'image/ktx2',
  '.riv': 'application/octet-stream',
};

function resolveFile(urlPath) {
  let p = decodeURIComponent(urlPath.split('?')[0]);
  const abs = path.normalize(path.join(ROOT, p));
  if (!abs.startsWith(ROOT)) return null;
  const candidates = [abs, path.join(abs, 'index.html'), abs + '.html'];
  for (const c of candidates) {
    try { if (fs.statSync(c).isFile()) return c; } catch {}
  }
  return null;
}

function serveFile(req, res, file) {
  const stat = fs.statSync(file);
  const type = MIME[path.extname(file).toLowerCase()] || 'application/octet-stream';
  const headers = { 'Content-Type': type, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' };
  const range = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
  if (range) {
    let start = range[1] ? parseInt(range[1], 10) : 0;
    let end = range[2] ? parseInt(range[2], 10) : stat.size - 1;
    if (!range[1] && range[2]) { start = stat.size - parseInt(range[2], 10); end = stat.size - 1; }
    if (start >= stat.size || end >= stat.size || start > end) {
      res.writeHead(416, { 'Content-Range': `bytes */${stat.size}` }); return res.end();
    }
    res.writeHead(206, { ...headers, 'Content-Range': `bytes ${start}-${end}/${stat.size}`, 'Content-Length': end - start + 1 });
    if (req.method === 'HEAD') return res.end();
    return fs.createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(200, { ...headers, 'Content-Length': stat.size });
  if (req.method === 'HEAD') return res.end();
  fs.createReadStream(file).pipe(res);
}

function proxyDato(body, preview) {
  return new Promise((resolve, reject) => {
    const r = https.request({
      host: 'graphql.datocms.com', path: preview ? '/preview' : '/', method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', Authorization: `Bearer ${DATO_TOKEN}` },
    }, (up) => { let d = ''; up.on('data', (c) => (d += c)); up.on('end', () => resolve({ status: up.statusCode, body: d })); });
    r.on('error', reject); r.end(body);
  });
}

// Rewrites remote DatoCMS asset URLs in GraphQL responses to the local mirror.
const localizeAssets = (s) => s.replace(/https:\/\/www\.datocms-assets\.com\//g, '/dato/');

function handleGraphql(req, res) {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', async () => {
    const preview = req.url.includes('preview');
    let key;
    try { const j = JSON.parse(body); key = crypto.createHash('sha1').update(JSON.stringify([j.query, j.variables || {}, preview])).digest('hex'); }
    catch { res.writeHead(400); return res.end('bad request'); }
    const file = path.join(CACHE, key + '.json');
    if (fs.existsSync(file)) {
      res.writeHead(200, { 'Content-Type': 'application/json' }); return res.end(fs.readFileSync(file));
    }
    try {
      const up = await proxyDato(body, preview);
      const out = localizeAssets(up.body);
      if (up.status === 200) { fs.mkdirSync(CACHE, { recursive: true }); fs.writeFileSync(file, out); }
      res.writeHead(up.status, { 'Content-Type': 'application/json' }); res.end(out);
    } catch (e) {
      res.writeHead(502, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ errors: [{ message: 'offline and not cached' }] }));
    }
  });
}

http.createServer((req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
  if (req.url.startsWith('/__graphql') && req.method === 'POST') return handleGraphql(req, res);
  // Mirror the original host: deep app routes 301 to "/" (they are only reachable via in-app navigation).
  if (/^\/(about|explore|navigation|chapter(\/[^/?]*)?)\/?(\?.*)?$/.test(req.url)) {
    res.writeHead(301, { Location: '/' }); return res.end();
  }
  const file = resolveFile(req.url);
  if (file) return serveFile(req, res, file);
  res.writeHead(404, { 'Content-Type': 'text/plain' }); res.end('Not found');
}).listen(PORT, () => console.log(`findworkhappiness clone → http://localhost:${PORT}/`));
