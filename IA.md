# https://www.findworkhappiness.com/

Source: https://www.findworkhappiness.com/ · site/ — production Nuxt static build, static payload dir 1758021745
Status: **measured-from-mirror** · production approved: **false**
17 routes · 6 templates · 20 unique sections

> Generated from `ia.json` by `build.mjs`. Edit the JSON, not this file.

## Shape of the site

The largest 3 templates (Chapter summary, Intro / book cover, Explore map) account for 14 of 17 routes (82%). The remaining 3 routes span 3 templates.

| template | routes | share |
|---|---:|---:|
| Chapter summary | 12 | 71% |
| Intro / book cover | 1 | 6% |
| Explore map | 1 | 6% |
| Chapter list | 1 | 6% |
| About the book | 1 | 6% |
| Download formats | 1 | 6% |

## Page chrome

**16 routes carry chrome = `app`** — Intro / book cover, Explore map, Chapter summary, Chapter list, About the book.

**1 routes carry chrome = `none`** — Download formats.

## Sections by reuse

How widely a section is shared determines whether it belongs in a shared
component library or stays local to its page.

| section | category | templates | routes | scope |
|---|---|---:|---:|---|
| `shell.header-nav` | SHELL | 5 | 16 | Present on all 16 app routes; the Download pill is hidden on the 12 chapter routes. |
| `shell.bottom-menu` | SHELL | 5 | 16 | Present on all 16 app routes (not rendered at 390px on the explore map). |
| `runtime.webgl-stage` | RUNTIME | 5 | 16 | Behind all 16 app routes. |
| `runtime.cursor` | RUNTIME | 5 | 16 | On all 16 app routes, desktop/hover devices only. |
| `media.audio-player` | MEDIA | 2 | 13 | On 13 routes: fixed at the bottom of the intro, in-flow above the card on the 12 chapter routes. |
| `chapter.header` | CHAPTER | 1 | 12 | On the 12 chapter routes. |
| `chapter.body` | CHAPTER | 1 | 12 | On the 12 chapter routes. |
| `chapter.pager` | CHAPTER | 1 | 12 | On the 12 chapter routes. |
| `shell.footer` | SHELL | 1 | 1 | Only on the 1 About route. |
| `runtime.preloader` | RUNTIME | 1 | 1 | Only on the 1 intro route, first load only. |
| `runtime.sound-gate` | RUNTIME | 1 | 1 | Only on the 1 intro route, until the visitor enters. |
| `hero.book-intro` | HERO | 1 | 1 | Only on the 1 intro route. |
| `hero.about-title` | HERO | 1 | 1 | Only on the 1 About route. |
| `navigation.explore-map` | NAVIGATION | 1 | 1 | Only on the 1 explore route. |
| `navigation.chapter-index` | NAVIGATION | 1 | 1 | Only on the 1 navigation route. |
| `content.about-book` | CONTENT | 1 | 1 | Only on the 1 About route. |
| `content.about-story` | CONTENT | 1 | 1 | Only on the 1 About route (2 instances). |
| `gallery.illustration-strip` | GALLERY | 1 | 1 | Only on the 1 About route (2 instances). |
| `cta.download-closer` | CONVERSION | 1 | 1 | Only on the 1 About route. |
| `cta.download-formats` | CONVERSION | 1 | 1 | Only on the 1 formats route. |

**5 shared sections** appear in more than one template and belong in a component library.

**15 single-use sections** appear in exactly one template. Building these
as "reusable" components up front would be speculative — keep them page-local
until a second caller actually appears.

## Templates

### Intro / book cover — `template.intro`

1 route · `/` · chrome: **app**

| # | category | section | |
|---:|---|---|---|
| 1 | RUNTIME | `runtime.preloader` | page-local |
| 2 | SHELL | `shell.header-nav` | shared ×5 |
| 3 | HERO | `hero.book-intro` | page-local |
| 4 | MEDIA | `media.audio-player` | shared ×2 |
| 5 | RUNTIME | `runtime.sound-gate` | page-local |
| 6 | SHELL | `shell.bottom-menu` | shared ×5 |
| 7 | RUNTIME | `runtime.webgl-stage` | shared ×5 |
| 8 | RUNTIME | `runtime.cursor` | shared ×5 |

### Explore map — `template.explore`

1 route · `/explore` · chrome: **app**

| # | category | section | |
|---:|---|---|---|
| 1 | SHELL | `shell.header-nav` | shared ×5 |
| 2 | NAVIGATION | `navigation.explore-map` | page-local |
| 3 | SHELL | `shell.bottom-menu` | shared ×5 |
| 4 | RUNTIME | `runtime.webgl-stage` | shared ×5 |
| 5 | RUNTIME | `runtime.cursor` | shared ×5 |

### Chapter summary — `template.chapter`

12 routes · `/chapter/{slug}` · chrome: **app**

| # | category | section | |
|---:|---|---|---|
| 1 | SHELL | `shell.header-nav` | shared ×5 |
| 2 | MEDIA | `media.audio-player` | shared ×2 |
| 3 | CHAPTER | `chapter.header` | page-local |
| 4 | CHAPTER | `chapter.body` | page-local |
| 5 | CHAPTER | `chapter.pager` | page-local |
| 6 | SHELL | `shell.bottom-menu` | shared ×5 |
| 7 | RUNTIME | `runtime.webgl-stage` | shared ×5 |
| 8 | RUNTIME | `runtime.cursor` | shared ×5 |

### Chapter list — `template.chapter-index`

1 route · `/navigation` · chrome: **app**

| # | category | section | |
|---:|---|---|---|
| 1 | SHELL | `shell.header-nav` | shared ×5 |
| 2 | NAVIGATION | `navigation.chapter-index` | page-local |
| 3 | SHELL | `shell.bottom-menu` | shared ×5 |
| 4 | RUNTIME | `runtime.webgl-stage` | shared ×5 |
| 5 | RUNTIME | `runtime.cursor` | shared ×5 |

### About the book — `template.about`

1 route · `/about` · chrome: **app**

| # | category | section | |
|---:|---|---|---|
| 1 | SHELL | `shell.header-nav` | shared ×5 |
| 2 | HERO | `hero.about-title` | page-local |
| 3 | CONTENT | `content.about-book` | page-local |
| 4 | GALLERY | `gallery.illustration-strip` | page-local |
| 5 | CONTENT | `content.about-story` | page-local |
| 6 | CONVERSION | `cta.download-closer` | page-local |
| 7 | SHELL | `shell.footer` | page-local |
| 8 | SHELL | `shell.bottom-menu` | shared ×5 |
| 9 | RUNTIME | `runtime.webgl-stage` | shared ×5 |
| 10 | RUNTIME | `runtime.cursor` | shared ×5 |

### Download formats — `template.download-formats`

1 route · `/formats/` · chrome: **none**

| # | category | section | |
|---:|---|---|---|
| 1 | CONVERSION | `cta.download-formats` | page-local |

## Section reference

### SHELL

_Fixed chrome shared by the app routes: top navigation pills, bottom chapter/explore menu, footer._

**`shell.header-nav`** — Fixed top bar: two white pill links ('Chapter summaries', 'About the book') on the left and a 'Download' pill with a tilted book thumbnail on the right. Pills wipe to an alternate label on hover.

· Present on all 16 app routes; the Download pill is hidden on the 12 chapter routes. · appears on 16 routes

**`shell.bottom-menu`** — Fixed bottom-centre pill reading 'Chapter' / 'Explore' around a round dark toggle button that switches between the chapter list and the explore map.

· Present on all 16 app routes (not rendered at 390px on the explore map). · appears on 16 routes

**`shell.footer`** — Yellow full-width bar at the very end of the About page: copyright line on the left, underlined 'Visit my online portfolio' link on the right.

· Only on the 1 About route. · appears on 1 routes

### RUNTIME

_Utility UI that is part of the experience engine rather than page content: preloader, sound gate, WebGL stage, custom cursor._

**`runtime.preloader`** — First-load loader on sage background: giant condensed number words counting up ('ONE … HUNDRED'), the book cover rising with a drop shadow, and a 'Loading Chapters' label; dismisses into the intro.

· Only on the 1 intro route, first load only. · appears on 1 routes

**`runtime.sound-gate`** — Yellow 'Enter without sound' pill (bottom-right) with a muted-speaker icon; the alternative to the intro's arrow button, which enters with sound on.

· Only on the 1 intro route, until the visitor enters. · appears on 1 routes

**`runtime.webgl-stage`** — Fixed full-screen WebGL canvas rendering the 3D book and the illustrated city backdrop, plus the drag grid that pans it.

· Behind all 16 app routes. · appears on 16 routes

**`runtime.cursor`** — Custom canvas cursor (open-hand / grabbing / pointer states) that replaces the system cursor on hover-capable devices.

· On all 16 app routes, desktop/hover devices only. · appears on 16 routes

### HERO

_Page-opening composition._

**`hero.book-intro`** — Centred stack of slightly rotated white paper cards holding the author portrait badge with circular 'THE NEW BOOK' text, the book wordmark, a one-line tagline (h1), the author signature, and a round yellow arrow button that enters the site.

· Only on the 1 intro route. · appears on 1 routes

**`hero.about-title`** — Viewport-high opener of the About page: giant 'ABOUT' condensed type behind a tilted 3D book, the author signature and an animated hot-air balloon.

· Only on the 1 About route. · appears on 1 routes

### MEDIA

_Audio playback UI for book/chapter narration._

**`media.audio-player`** — White pill audio player: author avatar, title ('CH. BOOK SYNOPSIS' or the chapter number), play button, elapsed time, waveform/timeline canvas, total duration.

· On 13 routes: fixed at the bottom of the intro, in-flow above the card on the 12 chapter routes. · appears on 13 routes

### NAVIGATION

_Content whose job is finding chapters: the draggable illustrated map and the chapter list._

**`navigation.explore-map`** — Draggable illustrated city map (WebGL) with chapter titles floating over their scenes, and a 'Drag around to find chapters' hint chip with a yellow icon that follows the cursor.

· Only on the 1 explore route. · appears on 1 routes

**`navigation.chapter-index`** — Full-screen black chapter list: vertically scrolling 'CH. 01…12' numerals with a hover preview, a 'Scroll through chapters' side label, top links ('Order the book', the author's name), an animated book in the centre and a close button.

· Only on the 1 navigation route. · appears on 1 routes

### CHAPTER

_The parts of a single chapter summary page._

**`chapter.header`** — Top of the chapter paper card: small 'Ch.' label, the chapter number as a giant condensed word (e.g. 'One'), and the chapter headline (h2, two clauses joined by an em dash), over a line-drawn chapter illustration.

· On the 12 chapter routes. · appears on 12 routes

**`chapter.body`** — Chapter summary prose under the header rule: 3–4 paragraphs (90–167 words) with bold and underlined emphasis marks.

· On the 12 chapter routes. · appears on 12 routes

**`chapter.pager`** — Fixed chapter controls: round close (X) button top-right and white 'Prev' / dark 'Next' pills at the bottom corners, linking to adjacent chapters.

· On the 12 chapter routes. · appears on 12 routes

### CONTENT

_Editorial prose blocks about the book and its author._

**`content.about-book`** — First About copy block: small 'Intro to the book' eyebrow, a large condensed first-person heading, and story paragraphs about the author's working life, set right of a large animated line-drawn illustration.

· Only on the 1 About route. · appears on 1 routes

**`content.about-story`** — Two-column story block: a large condensed first-person heading on one side and story paragraphs on the other. Appears twice, each one preceded by an illustration strip.

· Only on the 1 About route (2 instances). · appears on 1 routes

### GALLERY

_Image-only illustration strips._

**`gallery.illustration-strip`** — Full-width row of tall illustration figures, 2 columns below 650px and 4 columns at 650px and up.

· Only on the 1 About route (2 instances). · appears on 1 routes

### CONVERSION

_Blocks whose job is getting the book: download/order actions._

**`cta.download-closer`** — About page closer over a full-width bottom illustration: centred animated illustration/heading, a 4-figure stats row about the book (word count, copies sold, illustrated scenes, pages), and a Download pill with the tilted book.

· Only on the 1 About route. · appears on 1 routes

**`cta.download-formats`** — Standalone download page: two centred cards, PRINT BOOK (cover image + 'Download PDF') and AUDIOBOOK (cover image + 'Download Audio'), on a colour-changing background.

· Only on the 1 formats route. · appears on 1 routes
