# findworkhappiness.com — local mirror

Run: `npm start` → http://localhost:4173/  (Node 18+, no dependencies)

- `site/` — the original production Nuxt build (HTML, `_nuxt` JS chunks, fonts, cursors), 3D book
  (glTF/bin/KTX2 + Basis transcoder), Rive animations, audio, about textures, DatoCMS media (`site/dato/`),
  Rive wasm (`site/vendor/`), and the `/formats/` download page.
- `server.js` — static server with Range support (audio scrubbing), the same 301s the original host
  sends for deep routes (`/about`, `/explore`, `/navigation`, `/chapter/*` → `/`), and a cached DatoCMS
  GraphQL endpoint (`site/__graphql/cache`; proxies to DatoCMS only on a cache miss).

Patches applied to the original bundle (everything else is byte-for-byte):
- `https://www.datocms-assets.com/` → `/dato/`
- `https://graphql.datocms.com/` → `/__graphql/`
- unpkg `rive.wasm` → `/vendor/rive.wasm`
- absolute `https://www.findworkhappiness.com/` href/src → `/`

Still remote: the PDF / audiobook ZIP links on `/formats/` (book.findworkhappiness.com).
Known 404 shared with the original: `/riv/book-flip.riv` (missing on their server too).


## Information architecture

`ia.json` is the only IA file to hand-edit. `IA.md` and `matrix.csv` are **generated** from it — never edit them.

```bash
node validate.mjs   # hard checks: route sum, template count, section references, categories
node build.mjs      # regenerates IA.md (readable doc) and matrix.csv (section × template)
```

What the data shows (17 routes, 6 templates, 20 sections, measured from the mirror via in-app navigation):

- 12 of 17 routes (71%) are chapter summaries sharing one template; the other 5 routes are 5 one-off templates (intro, explore map, chapter list, about, download formats).
- 5 sections are shared: four fixed layers on all 16 app routes (header pills, bottom Chapter/Explore menu, WebGL stage, custom cursor) and the audio player on 13. The other 15 are page-local.
- `/formats/` sits outside the app: plain static HTML with no app chrome (`chrome: none`). Every other route sits on the same full-screen WebGL stage.
- `validate.mjs` prints 5 informational "scope vs computed" notes. None is an error: each flagged number is a true secondary fact written next to the correct route count — a subset (Download pill hidden on the 12 chapter routes; 12 of the audio player's 13 routes), a viewport width (390px), or an instance count (2 story blocks and 2 illustration strips on /about). Don't "fix" them to match.
- Sections carry no `implementedBy`, because there is no component source: `site/` is the compiled build.
