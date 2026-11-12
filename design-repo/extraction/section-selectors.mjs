// Shared section-id -> selector map (single source for measure_sections.mjs and parity.mjs).
// Keep the keys identical to the section contract ids in sections/*.json; verify_all.py checks this.
// routes: routes on which the section is looked up; flow=false: fixed/overlay UI (takes no page height).
// section contract id -> { routes, selector, flow }. flow=false: fixed/overlay UI (takes no page height).
export const SECTION_SELECTORS = {
  'shell.header-nav': { routes: ['/', '/explore', '/chapter/one', '/navigation', '/about'], selector: 'header.fixed', flow: false },
  'shell.bottom-menu': { routes: ['/', '/explore', '/chapter/one', '/navigation', '/about'], selector: 'div.menu-b', flow: false },
  'runtime.preloader': { routes: [], selector: null, flow: false },
  'runtime.sound-gate': { routes: ['/'], selector: 'button.btn-no-sound', flow: false },
  'runtime.cursor': { routes: ['/', '/explore', '/chapter/one', '/navigation', '/about'], selector: 'canvas.fixed.z-2', flow: false },
  'runtime.webgl-stage': { routes: ['/', '/explore', '/chapter/one', '/navigation', '/about'], selector: 'div.gl.fixed', flow: false },
  'hero.book-intro': { routes: ['/'], selector: '.home-mask-wrap', flow: false },
  'media.audio-player': { routes: ['/', '/chapter/one'], selector: 'article.sound', flow: true },
  'navigation.explore-map': { routes: ['/explore'], selector: 'div.thec', flow: false },
  'navigation.chapter-index': { routes: ['/navigation'], selector: 'div.menu.fixed', flow: false },
  'chapter.header': { routes: ['/chapter/one'], selector: 'h1.relative', flow: true, group: 'chapterHeader' },
  'chapter.body': { routes: ['/chapter/one'], selector: 'div.txt', flow: true },
  'chapter.pager': { routes: ['/chapter/one'], selector: '.js-chapter-ui nav', flow: false },
  'hero.about-title': { routes: ['/about'], selector: 'div.relative.ui-height', flow: true },
  'content.about-book': { routes: ['/about'], selector: 'div.js-book-end', flow: true },
  'gallery.illustration-strip': { routes: ['/about'], selector: 'div.grid.grid-cols-2', flow: true, all: true },
  'content.about-story': { routes: ['/about'], selector: 'section.py-75', flow: true, all: true },
  'cta.download-closer': { routes: ['/about'], selector: 'section.relative.pb-100', flow: true },
  'shell.footer': { routes: ['/about'], selector: 'footer', flow: true },
  'cta.download-formats': { routes: ['/formats/'], selector: 'body > div', flow: true, all: true },
};
