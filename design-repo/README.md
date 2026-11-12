# Design-repo: single-book promotional site (reference: findworkhappiness.com)

An AI-ready, machine-validated design system extracted from a byte-for-byte mirror of the production
build of a single-book promotional site. A generator uses it to compose new pages (PageSpecs)
from approved sections, tokens and asset roles, without inventing colours, copy budgets or structure,
and without reproducing the source's identity.

**Status:** `design-review-pending` · `productionApproved: false` · policy approval
`defined-pending-architecture-review` (no architecture decision recorded). Repository version 1.0.0,
PageSpec 1.0.0, allowlist 1.0.0.

## What the source is (evidence, not assumption)

- Category **book-promotion**: one book, 12 chapter summaries with narration, an audio synopsis,
  free PDF + audiobook downloads (`/formats/`), one external retailer order link and one author
  portfolio link. No pricing, no sign-up, no dashboard. See `policy/design-policy.json`.
- Source stack (documentation only; it never shapes ids, tokens or validator logic): Nuxt 2 static
  generate, Tailwind 2.2.19, GSAP, three.js (glTF + KTX2/Basis), Rive, DatoCMS content, HTML5 audio.
  `/formats/` is plain static HTML outside the app.

### Structurally unusual facts

1. **Deep routes are app-internal.** A direct load of `/about`, `/explore`, `/navigation` or any
   `/chapter/*` answers `301 -> /` on the original host, and the clone server reproduces that. Those
   pages exist only through in-app navigation (router push or clicking). They are still real,
   content-bearing routes and each is mapped to a template. Every measurement and parity capture
   therefore starts at `/`, clicks the site's own sound gate and navigates in-app.
2. **`/formats/` is a separate static page** with its own stylesheet and its own font family names
   ("Founders Bold" / "Founders Condensed", mapped to `font.display`). It has no shell, runtime or WebGL.
3. **Fluid root size.** `html { font-size: calc(1000vw / var(--size)) }` with `--size` 375 below
   650px and 1520 at >= 650px: 1 design unit = 0.1rem and everything scales with the viewport. There is
   one layout breakpoint (650px, `s:` prefix) plus hover-capable media queries for cursor/hover effects.
4. **Fixed chrome on every app page** (header pills, bottom menu, WebGL stage, canvas cursor) takes
   no page height; the page itself scrolls a transformed wrapper.
5. **No reduced-motion handling in the source** (0 `prefers-reduced-motion` hits). Every section
   contract defines the `reducedMotionFallback` a generated page must implement.
6. **The source has no reviews, ratings or testimonials.** The PageSpec has no rating field and
   `GENERATED_MODE_RATING` is documented as not applicable (nothing grounded to match); the nearest
   real claim class, the About closer's book statistics, is blocked by `GENERATED_MODE_STATISTIC`.
7. **Verified from a fresh `git clone` (R12/R14).** The project is a private git repository
   (initialised after the build, on the owner's request). A fresh clone of commit `705cb2d` passes the
   baseline audit (26/26), `verify_all` (18/18, including the sibling-source pins), the adversarial
   suite (95/95 + 20/20), `prove_drift` (55/55) and `node validate.mjs`; `server.js` serves the clone
   from the checkout. The design-repo alone, copied into an empty OS temp directory, also passes (see
   CHANGELOG).

## Counts (recomputed from disk by `extraction/verify_all.py`; the builder rewrites these markers)

| | |
|---|---|
| Section contracts | <!--count:sections-->20 |
| Templates (page shapes) | <!--count:templates-->6 |
| Routes (each mapped once) | <!--count:routes-->17 |
| Asset roles | <!--count:assetRoles-->27 |
| Catalog tokens | <!--count:tokens-->131 |

## Templates and routes

| Template | Family | Routes | Node sequence (fixed chrome omitted) |
|---|---|---|---|
| `intro` | home | `/` | runtime.preloader, hero.book-intro, media.audio-player, runtime.sound-gate |
| `explore` | navigation | `/explore` | navigation.explore-map |
| `chapter` | article | `/chapter/one` ... `/chapter/twelve` (12) | media.audio-player, chapter.header, chapter.body, chapter.pager |
| `chapter-index` | navigation | `/navigation` | navigation.chapter-index (a real content route, not an overlay) |
| `about` | about | `/about` | hero.about-title, content.about-book, gallery.illustration-strip (a), content.about-story (a), gallery.illustration-strip (b), content.about-story (b), cta.download-closer, shell.footer |
| `download-formats` | conversion | `/formats/` | cta.download-formats (print), cta.download-formats (audiobook) |

App templates also require `shell.header-nav`, `shell.bottom-menu`, `runtime.webgl-stage` and
`runtime.cursor` (measured on all five app routes at 1440px). Exact sequences: `templates/templates.json`.

Heights at 1440px (`extraction/measured-values.json` `sectionHeights`): chapter page 1626px
(audio 63, header 272, body 483); about page 6590px (hero 900, book 1133, strips 448 + 448, stories
1256 + 1154, closer 1182, footer 70). Largest in-flow share: 19% (about story). No HERO above 900px.

Measured corrections to the original brief: the about page's "I never set out to be a leader"
heading belongs to `content.about-book`; the two `content.about-story` headings are "I had to leave
home to build a better life" and "This is not an all-or-nothing endeavor". The About closer's four
book statistics sit in the same `<section>` as the Download button, so they are a `stat-block`
component inside `cta.download-closer` (CTA class), not a separate proof section.

## Layout

```
registry.manifest.json      status, counts, versions, policy binding, entry points (inside the package only)
policy/design-policy.json   category, n0-design-constraints-common 0.1.0 + local extension, approval (pending)
tokens/00-foundation/       color, typography, radius, spacing, breakpoint, elevation, motion, motion-patterns
tokens/10-semantic/         text.* / surface.* roles -> foundation colours
tokens/20-component/        component-scoped token refs
tokens/30-layout/           widths, gutters, gallery columns
tokens/themes/light.json    the only theme the source ships
tokens/llm/                 component-allowlist.json, token-catalog.json, token-policy.json
primitives/ components/     atomic and composed building blocks (evidence-cited)
sections/                   one contract per section type (source + semantic split, content budgets,
                            constraints, closed motion + reducedMotionFallback, structured responsive,
                            retrievalEligible, asset slots, generatedAssetRoles, measured heights)
assets/asset-roles.json     27 roles, closed availability enum, substitutes, licensing
templates/templates.json    6 templates with structured nodes + the 17-route map
compatibility/graph.json    11 rhythm/position rules with severity and named exceptions
schema/                     pagespec.schema.json (Draft-07, closed), section-contract.schema.json,
                            source-patterns.json, semantic_validate.py, examples/, tests/adversarial_test.py
extraction/                 evidence/ (tracked, line-citeable, sha256-pinned), measured-values.json,
                            verify_all.py, wrapper_gate.py, policy_hash.py, prove_drift.py, build_repo.py,
                            extract_evidence.mjs, measure_sections.mjs, section-selectors.mjs, parity.mjs
```

## Modes and generation rules

Every PageSpec declares `mode`:

- `reference`: faithful reconstruction of the source. Real copy and real assets are allowed as
  evidence (`schema/examples/reference.chapter-one.pagespec.json`).
- `generated`: a new page for someone else. The semantic validator rejects the source brand and its
  variants, the author's name and handles, source URLs and download/store links, source CTAs, source
  copy (exact phrases plus any 6-word run shared with the measured source text), the book statistics,
  proprietary media paths, and any asset role that is not `generation-safe` (pinned in code). Absolute
  URLs must use reserved `.example` / `.invalid` hosts. Generated examples: intro, chapter, about,
  download-formats.

### Assets and licensing

The source is a real, live site by a real, named author. Cover art, chapter and about illustrations,
3D book textures, Rive files, the wordmark, text badges, the author's portrait and signature and the
narrated audio (the author's voice) are proprietary: `reference-only` or `blocked-for-generation`,
each with `generationSafeSubstitutes` (generated brand mark, fictional people, generated signature,
generated product visuals and illustrations, placeholder URLs and audio, original copy).

**Fonts:** Founders Grotesk and Founders Grotesk X-Condensed are commercial Klim Type Foundry
typefaces. The mirrored woff2 files are reference-only. A generated deliverable may use `font.text` /
`font.display` only when it declares `fontLicence: "licensed-by-deployer"`; otherwise it must use
`font.fallback-sans` (enforced by `GENERATED_MODE_FONT_LICENCE`).

## Tokens

Colours (Tailwind names of the original config): black #222324, gray-3 #b9b8b1, gray-4 #a5bab3,
white #f9f8f3, white-classic #ffffff, white-off #f4f3eb, yellow #ffeb35, page background sage #9ab5ac.
Type: `font-1` Founders Grotesk 400/400 italic/700, `font-2` X-Condensed Bold 700; sizes kept only when
rendered (design units 14-492, e.g. 15, 18, 20, 23, 24, 29, 35, 55, 100, 170, 180, 300). Radius: pill
9999px only (plus the preloader book spine). Shadows: paper -1px 9px 10px rgba(0,0,0,.06) and
-2px 9px 10px rgba(0,0,0,.1), Tailwind shadow-xl. Motion: GSAP CustomEase "snappy", power1, expo,
back.in, CSS clip-path reveals with cubic-bezier(.19,1,.22,1), hover spring cubic-bezier(.34,1.56,.64,1).
PageSpecs reference tokens only through `node.style`; raw colours, raw spacing, unknown tokens,
unsupported fonts and colour pairs outside the theme's allowed pairs are rejected.

## Running the checks

```bash
python3 extraction/verify_all.py            # all drift-proofed checks (exit 1 on FAIL)
python3 schema/semantic_validate.py --examples
python3 schema/tests/adversarial_test.py    # every mutation rejected, every control passes
python3 extraction/prove_drift.py           # every check proven to catch an injected fault
python3 extraction/wrapper_gate.py          # R9 gate alone
```

Requirements: Python 3 with `jsonschema` (Draft-07). Optional re-measure / rebuild tools need Node 20
and Playwright; their machine paths come from the environment, never from the repo:

```bash
node extraction/extract_evidence.mjs                      # re-extract evidence from ../site
BASE_URL=http://localhost:4173 PLAYWRIGHT_MODULE=<playwright module or path> node extraction/measure_sections.mjs
LIVE_URL=https://www.findworkhappiness.com BASE_URL=http://localhost:4173 PLAYWRIGHT_MODULE=<...> node extraction/parity.mjs
python3 extraction/build_repo.py                          # regenerate tokens/contracts/registries; citations re-pointed by needle
```

When the source changes (R16): re-extract, re-measure, rebuild, run `verify_all` (the
`sibling-sources` check fails when `../site` no longer matches its pins), bump the version, record it
in the CHANGELOG.

## Parity (R12)

Live site vs clone, measured by `extraction/parity.mjs` at 1440x900. Both sides follow the same in-app path with the same waits. The site's own "Enter without sound" gate is clicked on both sides; there is no cookie banner and nothing is masked. Each section's crop is compared pixel by pixel. Similarity = 1 - the fraction of pixels whose luminance differs by more than 30. Numbers are from `extraction/evidence/parity-results.json` (sha256-pinned in `measured-values.json`):

- 39 section instances captured on both sides in each of 2 runs; **every one passes the 0.80 gate**.
- Average similarity **0.9961**; the two runs agree (largest run-to-run change 0.0016, tolerance 0.02).
- Lowest: `/chapter/one|chapter.body|0` 0.8671, `/about|hero.about-title|0` 0.994, `/about|content.about-book|0` 0.9955.
- `chapter.body` scores 0.8671 in both runs. The cause is a measurement limit, not a clone difference: the site's momentum scroller settled a fraction of a pixel apart on the two sides (crop tops 120 vs 121px in both runs). Text rasterised at a different sub-pixel offset differs at its edges, and whole-pixel alignment cannot undo that. When both sides land on the same offset, the same section scores 1.0 (an earlier run, and 6 of 6 isolated checks). It passes the gate, so no exception is recorded; it is reported here rather than masked.
- Whole-screen numbers from before this build (per screen, not per section) are in `measured-values.json` under `parity.screenLevel`.

Parity exceptions: none.

## Open human decisions

1. Ratify (or change) the `book-promotion` classification and the binding to
   `n0-design-constraints-common` 0.1.0 + local extension (`policy/design-policy.json`, currently
   `defined-pending-architecture-review`, `architectureDecisionRecorded: false`).
2. Production approval of this design-repo (`productionApproved: false`).
3. Any parity exception listed above (`status: "pending human approval"`, `approvedBy: null`).

No IR file was created or touched.
