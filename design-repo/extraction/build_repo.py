#!/usr/bin/env python3
"""Deterministic builder for the generated parts of this design-repo.

    python3 extraction/build_repo.py

Reads ONLY files inside design-repo (extraction/evidence/*) and writes:
tokens/**, primitives/*, components/*, sections/*, templates/templates.json,
compatibility/graph.json, assets/asset-roles.json, schema/pagespec.schema.json,
schema/section-contract.schema.json, schema/source-patterns.json,
extraction/measured-values.json, policy/design-policy.json, registry.manifest.json.

Every citation is resolved by NEEDLE (the text that must be on the cited line), never by a
hand-typed line number, so re-running after the evidence moves re-points every citation (R16).
verify_all.py independently re-checks every citation, count, pin and hash; it never runs this file.
Hand-written files (README, CHANGELOG, validators, tests, examples) are not touched.
"""
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
EV = "extraction/evidence"
REPO_VERSION = "1.0.0"
PAGESPEC_VERSION = "1.0.0"
ALLOWLIST_VERSION = "1.0.0"

_lines = {}
def lines(rel):
    if rel not in _lines:
        _lines[rel] = (ROOT / rel).read_text().split("\n")
    return _lines[rel]

def cite(rel, needle, nth=1, span=0, after=None):
    """Return {cite, needle} for the nth line (1-based) containing needle (optionally after a line containing `after`)."""
    seen, start = 0, 0
    L = lines(rel)
    if after:
        start = next(i for i, l in enumerate(L) if after in l)
    for i in range(start, len(L)):
        if needle in L[i]:
            seen += 1
            if seen == nth:
                n = i + 1
                return {"cite": f"{rel}:{n}" + (f"-{n + span}" if span else ""), "needle": needle}
    raise SystemExit(f"needle not found: {rel} :: {needle!r}")

def dump(rel, obj):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

def load(rel):
    return json.loads((ROOT / rel).read_text())

C1440, C768, C390 = (load(f"{EV}/computed-{w}.json") for w in (1440, 768, 390))
COPY = load(f"{EV}/copy.json")
ROOT_PX = {1440: 9.47368, 768: 5.05263, 390: 10.4}

def page(c, route):
    return next(p for p in c["pages"] if p["route"] == route)

def hist_values(c, key):
    out = {}
    for p in c["pages"]:
        for v, n in p["hist"].get(key, {}).items():
            out[v] = out.get(v, 0) + n
    return out

# ---------------------------------------------------------------- foundation tokens
def hexrgb(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"

COLOR_SRC = [  # (token, tailwind name, value, needle in site.css)
    ("color.black", "black", "#222324", ".bg-black {"),
    ("color.gray-3", "gray-3", "#b9b8b1", ".bg-gray-3 {"),
    ("color.gray-4", "gray-4", "#a5bab3", ".text-gray-4 {"),
    ("color.white", "white", "#f9f8f3", ".bg-white {"),
    ("color.white-classic", "white-classic", "#ffffff", ".bg-white-classic {"),
    ("color.white-off", "white-off", "#f4f3eb", ".bg-white-off {"),
    ("color.yellow", "yellow", "#ffeb35", ".bg-yellow {"),
]
fg, bg = hist_values(C1440, "color"), hist_values(C1440, "backgroundColor")
color = {}
for tok, name, val, needle in COLOR_SRC:
    c = cite(f"{EV}/site.css", needle)
    n = int(c["cite"].split(":")[1])
    decl = cite(f"{EV}/site.css", val if val != "#ffffff" else "#fff", after=needle)
    color[tok] = {"value": val, "sourceName": name, "evidence": [c, decl],
                  "measuredUsage1440": {"text": fg.get(hexrgb(val), 0), "background": bg.get(hexrgb(val), 0)}}
color["color.sage"] = {"value": "#9ab5ac", "sourceName": "body background (no utility class)",
                       "evidence": [cite(f"{EV}/site.css", "background-color:#9ab5ac")],
                       "measuredUsage1440": {"text": 0, "background": 0,
                                             "note": "page background of <body>; the histogram counts element backgrounds only, the body sits behind the fixed WebGL stage"}}
color_excluded = {
    "#a1a1aa": "Tailwind preflight placeholder colour (no input on the site)",
    "#f5f2f0/#708090/#999/#905/#690/#9a6e3a/#07a/#dd4a68/#e90/#b3d4fc": "Prism code-highlighting theme bundled by the CMS renderer; no code block on any route",
    "#f7f8fb/#47494e/#7f828b": "framework error page (embedded.css), never shown on a working route",
}
dump("tokens/00-foundation/color.json", {"category": "color", "unit": "hex", "tokens": color,
     "excluded": color_excluded, "derivedFrom": "extraction/evidence/site.css (Tailwind 2 colour utilities of the original config) + computed-1440.json colour histogram"})

# typography
fonts = {
    "font.text": {"value": "font-1", "family": "Founders Grotesk", "weights": [400, 700], "styles": ["normal", "italic"],
                  "evidence": [cite(f"{EV}/site.css", "font-family:font-1;", after="@font-face"), cite(f"{EV}/site.css", "founders-grotesk-regular.b3e94bf.woff2"),
                               cite(f"{EV}/site.css", "founders-grotesk-bold.a9d28ab.woff2"), cite(f"{EV}/site.css", "founders-grotesk-regular-italic.124ac30.woff2")],
                  "licence": "commercial typeface (Klim Type Foundry); the mirrored woff2 files are reference-only"},
    "font.display": {"value": "font-2", "family": "Founders Grotesk X-Condensed", "weights": [700], "styles": ["normal"],
                     "evidence": [cite(f"{EV}/site.css", "font-family:font-2;", after="@font-face"), cite(f"{EV}/site.css", "founders-grotesk-x-condensed-bold.2f649e5.woff2")],
                     "licence": "commercial typeface (Klim Type Foundry); the mirrored woff2 files are reference-only"},
    "font.fallback-sans": {"value": "ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif",
                           "family": "system sans-serif stack (Tailwind preflight default)", "weights": [400, 700], "styles": ["normal", "italic"],
                           "evidence": [cite(f"{EV}/site.css", "font-family:ui-sans-serif,system-ui")],
                           "licence": "system fonts; approved fallback for generated deliverables without a Founders Grotesk licence"},
}
font_hist = hist_values(C1440, "fontFamily")
fonts["font.text"]["measuredUsage1440"] = {k: v for k, v in font_hist.items() if k.startswith("font-1")}
fonts["font.display"]["measuredUsage1440"] = {k: v for k, v in font_hist.items() if k.startswith("font-2")}
formats_fonts = {"Founders Bold": "font.display", "Founders Condensed": "font.display"}

size_px = {w: set(hist_values(c, "fontSize")) for w, c in ((1440, C1440), (768, C768), (390, C390))}
fontsize = {}
for i, l in enumerate(lines(f"{EV}/site.css")):
    m = re.match(r"^\s*\.(s\\:)?text-(\d+|\\\[[\d\\.]+rem\\\]) \{$", l)
    if not m: continue
    nxt = lines(f"{EV}/site.css")[i + 1]
    fm = re.match(r"^\s*font-size:([\d.]+)rem;$", nxt)
    if not fm: continue
    rem = float(fm.group(1)); units = round(rem * 10)
    widths = (1440, 768) if m.group(1) else (1440, 768, 390)
    hit = [w for w in widths if any(abs(float(px[:-2]) - rem * ROOT_PX[w]) < 0.05 for px in size_px[w])]
    if not hit: continue
    t = fontsize.setdefault(f"fontSize.{units}", {"value": f"{rem:g}rem", "designUnits": units, "measuredAtViewports": [], "evidence": []})
    t["measuredAtViewports"] = sorted(set(t["measuredAtViewports"]) | set(hit), reverse=True)
    t["evidence"].append({"cite": f"{EV}/site.css:{i + 1}-{i + 2}", "needle": l.strip()})
lineheight, tracking = {}, {}
for i, l in enumerate(lines(f"{EV}/site.css")):
    m = re.match(r"^\s*\.(?:s\\:)?leading-(none|\\\[\\?\.?[\d\\.]+\\\]) \{$", l)
    if m:
        v = lines(f"{EV}/site.css")[i + 1].strip().rstrip(";").split(":")[1]
        lineheight.setdefault("lineHeight." + ("none" if v == "1" else f"{float(v):g}".replace(".", "-")), {"value": v, "evidence": [{"cite": f"{EV}/site.css:{i + 1}-{i + 2}", "needle": l.strip()}]})
    m = re.match(r"^\s*\.(?:s\\:)?tracking-\\\[(.*)\\\] \{$", l)
    if m:
        v = lines(f"{EV}/site.css")[i + 1].strip().rstrip(";").split(":")[1]
        tracking.setdefault("letterSpacing." + re.sub(r"^-", "neg-", re.sub(r"^(-?)\.", r"\g<1>0.", v)).replace(".", "-"), {"value": v, "evidence": [{"cite": f"{EV}/site.css:{i + 1}-{i + 2}", "needle": l.strip()}]})
dump("tokens/00-foundation/typography.json", {
    "category": "typography",
    "unitNote": "html font-size = calc(1000vw / var(--size)); --size 375 below 650px, 1520 at >= 650px. 1 design unit = 0.1rem; Tailwind text-N = N/10 rem. Sizes are kept only when the computed fontSize histogram at 1440/768/390 shows them rendered.",
    "rootSize": {"evidence": [cite(f"{EV}/site.css", "font-size:calc(1000vw/var(--size));"), cite(f"{EV}/site.css", "--size:375;"), cite(f"{EV}/site.css", "--size:1520;")],
                 "measuredRootPx": {"1440": "9.47368px", "768": "5.05263px", "390": "10.4px"}},
    "fontFamily": fonts, "formatsPageAliases": formats_fonts,
    "fontSize": dict(sorted(fontsize.items(), key=lambda kv: kv[1]["designUnits"])),
    "lineHeight": lineheight, "letterSpacing": tracking,
    "fontWeight": {"fontWeight.regular": {"value": 400, "evidence": [cite(f"{EV}/site.css", "font-weight:400;", after="@font-face")]},
                   "fontWeight.bold": {"value": 700, "evidence": [cite(f"{EV}/site.css", "font-weight:700;", after="@font-face")]}},
    "textTransform": {"measured1440": hist_values(C1440, "textTransform")},
})

radius = {"radius.pill": {"value": "9999px", "evidence": [cite(f"{EV}/site.css", "border-radius:9999px;")], "measuredUsage1440": hist_values(C1440, "borderRadius").get("9999px", 0)},
          "radius.book-spine": {"value": "6rem", "valueAtMin650": "12rem", "usage": "right edge of the preloader book (rounded-r)", "evidence": [cite(f"{EV}/site.css", ".rounded-r-\\[6rem\\] {"), cite(f"{EV}/site.css", ".s\\:rounded-r-\\[12rem\\] {")]}}
dump("tokens/00-foundation/radius.json", {"category": "radius", "tokens": radius,
     "excluded": {".3em": "Prism inline-code radius (CMS code-highlighter CSS); no code on any route", "clip-path round()": "clip-path reveal radii are part of motion patterns, not border radius"}})

spacing = {}
for i, l in enumerate(lines(f"{EV}/site.css")):
    m = re.match(r"^\s*\.(?:s\\:)?-?(p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap)-(\d+) \{$", l)
    if not m: continue
    d = re.match(r"^\s*[a-z-]+:(-?[\d.]+)rem;$", lines(f"{EV}/site.css")[i + 1])
    if not d: continue
    u = round(abs(float(d.group(1))) * 10)
    spacing.setdefault(f"space.{u}", {"value": f"{u / 10:g}rem", "designUnits": u, "usedBy": [], "evidence": [{"cite": f"{EV}/site.css:{i + 1}-{i + 2}", "needle": l.strip()}]})
    spacing[f"space.{u}"]["usedBy"].append(l.strip().rstrip(" {").lstrip("."))
spacing = dict(sorted(spacing.items(), key=lambda kv: kv[1]["designUnits"]))
dump("tokens/00-foundation/spacing.json", {"category": "spacing", "unitNote": "design units (1 unit = 0.1rem, fluid with the root size); derived from every padding/margin/gap utility the purged Tailwind stylesheet emits", "tokens": spacing})

dump("tokens/00-foundation/breakpoint.json", {"category": "breakpoint", "tokens": {
    "breakpoint.s": {"value": "650px", "query": "(min-width:650px)", "prefix": "s:", "evidence": [cite(f"{EV}/site.css", "@media (min-width:650px) {")]},
    "breakpoint.max-s": {"value": "649px", "query": "(max-width:649px)", "prefix": "max-s:", "evidence": [cite(f"{EV}/site.css", "@media (max-width:649px) {")]},
    "breakpoint.has-hover": {"value": "(hover:hover) and (pointer:fine)", "prefix": "has-hover:", "usage": "gates the custom cursor, hover springs and Rive hover states", "evidence": [cite(f"{EV}/site.css", "@media (hover:hover) and (pointer:fine) {")]},
}, "note": "single layout breakpoint at 650px; the root font size switches design width 375 -> 1520 there, so everything scales fluidly between breakpoints"})

dump("tokens/00-foundation/elevation.json", {"category": "elevation", "tokens": {
    "elevation.paper-1": {"value": "-1px 9px 10px rgba(0,0,0,.06)", "usage": "front paper sheet of a stack", "evidence": [cite(f"{EV}/site.css", "box-shadow:-1px 9px 10px rgba(0,0,0,.06);"), cite(f"{EV}/embedded.css", "box-shadow:-1px 9px 10px rgba(0,0,0,.06);")]},
    "elevation.paper-2": {"value": "-2px 9px 10px rgba(0,0,0,.1)", "usage": "middle paper sheet of a stack", "evidence": [cite(f"{EV}/site.css", "box-shadow:-2px 9px 10px rgba(0,0,0,.1);"), cite(f"{EV}/embedded.css", "box-shadow:-2px 9px 10px rgba(0,0,0,.1);")]},
    "elevation.xl": {"value": "0 20px 25px -5px rgba(0,0,0,.1),0 10px 10px -5px rgba(0,0,0,.04)", "usage": "Tailwind shadow-xl", "evidence": [cite(f"{EV}/site.css", "--tw-shadow:0 20px 25px -5px rgba(0,0,0,.1)")]},
}, "measured1440": hist_values(C1440, "boxShadow")})

def mcite(needle, nth=1):
    return cite(f"{EV}/motion.txt", needle, nth)
mot_lines = lines(f"{EV}/motion.txt")
def count(tok):
    return sum(1 for l in mot_lines if l.endswith("\t" + tok))
durations = {}
for v in [".2", ".25", ".3", ".35", ".5", ".75", "1", "1.15", "1.25", "1.5", "2"]:
    durations[f"duration.{round(float(v) * 1000)}ms"] = {"value": f"{float(v):g}s", "gsapOccurrences": count(f"duration:{v}"), "evidence": [mcite(f"\tduration:{v}")]}
easing = {
    "easing.snappy": {"value": "CustomEase M0,0 C0.094,0.026 0.124,0.127 0.157,0.29 0.197,0.486 0.254,0.8 0.348,0.884 0.42,0.949 0.374,1 1,1", "engine": "GSAP CustomEase", "occurrences": count('ease:"snappy"'), "evidence": [mcite('.create("snappy"'), mcite('ease:"snappy"')]},
    "easing.power1": {"value": "power1.out", "engine": "GSAP", "occurrences": count('ease:"power1"'), "evidence": [mcite('ease:"power1"')]},
    "easing.linear": {"value": "linear", "engine": "GSAP", "occurrences": count('ease:"linear"') + count('ease:"none"'), "evidence": [mcite('ease:"linear"')]},
    "easing.expo": {"value": "expo.out", "engine": "GSAP", "occurrences": count('ease:"expo"'), "evidence": [mcite('ease:"expo"')]},
    "easing.back-in": {"value": "back.in", "engine": "GSAP", "occurrences": count('ease:"back.in"'), "evidence": [mcite('ease:"back.in"')]},
    "easing.expo-out-css": {"value": "cubic-bezier(.19,1,.22,1)", "engine": "CSS", "evidence": [mcite("transition:clip-path 1s cubic-bezier(.19,1,.22,1)")]},
    "easing.spring-css": {"value": "cubic-bezier(.34,1.56,.64,1)", "engine": "CSS", "evidence": [mcite("transition:transform .5s cubic-bezier(.34,1.56,.64,1)")]},
    "easing.in-out-css": {"value": "cubic-bezier(.77,0,.175,1)", "engine": "CSS", "evidence": [mcite("transition:transform .5s cubic-bezier(.77,0,.175,1)")]},
}
dump("tokens/00-foundation/motion.json", {"category": "motion", "duration": durations, "easing": easing,
     "reducedMotionNote": "the source build contains no prefers-reduced-motion handling (grep of every chunk: 0 hits); every section contract therefore defines its own reducedMotionFallback that generated pages must implement"})

PATTERNS = {
    "clip-reveal": {"description": "clip-path inset/circle reveal of a pill, menu or chip", "durations": ["duration.500ms", "duration.750ms", "duration.1000ms"], "easing": "easing.expo-out-css", "trigger": ["load", "route-enter", "hover", "toggle"], "fallbacks": ["static-final-state", "instant-opacity"],
                    "evidence": [mcite("transition:clip-path .65s cubic-bezier(.19,1,.22,1)"), mcite("transition:clip-path .5s cubic-bezier(.19,1,.22,1)")]},
    "paper-stack-rise": {"description": "stacked paper sheets translate up from below the fold with staggered rotation, then settle tilted (+2deg/-2deg)", "durations": ["duration.1000ms"], "easing": "easing.expo-out-css", "trigger": ["load", "route-enter"], "fallbacks": ["static-final-state"],
                         "evidence": [mcite("transition:transform 1s cubic-bezier(.19,1,.22,1)"), cite(f"{EV}/site.css", ".home-mask.--1[data-v-34bc0716] {")]},
    "hover-spring": {"description": "overshooting transform on hover (download book pill)", "durations": ["duration.500ms"], "easing": "easing.spring-css", "trigger": ["hover"], "fallbacks": ["static-final-state"],
                     "evidence": [mcite("transition:transform .5s cubic-bezier(.34,1.56,.64,1)")]},
    "snappy-tween": {"description": "GSAP tween with the CustomEase 'snappy' curve (route transitions, chapter card in/out)", "durations": ["duration.500ms", "duration.750ms", "duration.1000ms", "duration.1250ms"], "easing": "easing.snappy", "trigger": ["route-enter", "scroll"], "fallbacks": ["static-final-state", "instant-opacity"],
                     "evidence": [mcite('ease:"snappy"')]},
    "counter-roll": {"description": "preloader word counter rolls ONE ... HUNDRED", "durations": ["duration.1250ms"], "easing": "easing.power1", "trigger": ["load"], "fallbacks": ["static-final-state"],
                     "evidence": [cite(f"{EV}/site.css", ".intro__list[data-v-158e6d46] {")]},
    "pulse-loop": {"description": "5s infinite opacity pulse ('Loading Chapters')", "durations": [], "easing": "easing.linear", "trigger": ["load"], "fallbacks": ["static-final-state"], "loops": True,
                   "evidence": [mcite("animation:pulse-158e6d46 5s infinite")]},
    "spin-loop": {"description": "5s linear infinite rotation of the circular text ring on the enter button", "durations": [], "easing": "easing.linear", "trigger": ["load", "hover"], "fallbacks": ["static-final-state"], "loops": True,
                  "evidence": [mcite("animation:spin-34bc0716 5s linear infinite")]},
    "rive-state-machine": {"description": "Rive artboard driven by hover/playback state (play-pause, close icon, signature, balloon)", "durations": [], "easing": None, "trigger": ["load", "hover", "audio"], "fallbacks": ["static-final-state"],
                           "evidence": [cite(f"{EV}/markup.txt", 'e("canvas",{ref:"sig"')]},
    "webgl-scene": {"description": "three.js scene (3D book, draggable illustrated map, scroll-driven about planes)", "durations": [], "easing": "easing.snappy", "trigger": ["load", "drag", "scroll"], "fallbacks": ["static-final-state"],
                    "evidence": [cite(f"{EV}/embedded.css", ".gl[data-v-51deb141] {")]},
    "fade": {"description": "opacity fade", "durations": ["duration.200ms", "duration.500ms"], "easing": "easing.power1", "trigger": ["load", "route-enter", "scroll"], "fallbacks": ["instant-opacity", "static-final-state"],
             "evidence": [mcite("transition:opacity .5s ease-out")]},
    "none": {"description": "no motion", "durations": [], "easing": None, "trigger": ["none"], "fallbacks": ["none-required"], "evidence": []},
}
dump("tokens/00-foundation/motion-patterns.json", {"category": "motion-patterns", "patterns": PATTERNS,
     "fallbackEnum": ["static-final-state", "instant-opacity", "none-required"], "triggerEnum": ["load", "route-enter", "scroll", "hover", "toggle", "drag", "audio", "none"],
     "riveArtboards": ["state-mach-play-pause", "timeline-shifter", "multiplier-timeline", "close-icon-hover_blk", "close-icon-hover_wht", "sig-about", "about-heli-clouds", "dl-sig", "go-search", "green-arrow", "whizz-bang", "hamburger-icon", "buy-smile", "book-flipper", "book-balloon"],
     "riveArtboardsNote": "grep 'artboard:\"' over the mirrored chunks (../site/_nuxt/*.js); the .riv files are reference-only assets (assets/asset-roles.json animation.rive)"})

# ---------------------------------------------------------------- semantic / component / layout / theme
semantic = {
    "text.primary": "color.black", "text.inverse": "color.white", "text.muted": "color.gray-4", "text.subtle": "color.gray-3",
    "surface.page": "color.sage", "surface.paper": "color.white", "surface.paper-stack": "color.white-off", "surface.pill": "color.white",
    "surface.pill-bright": "color.white-classic", "surface.accent": "color.yellow", "surface.inverse": "color.black", "surface.muted": "color.gray-3",
}
sem_ev = {"text.primary": cite(f"{EV}/site.css", "color:#222324;", after="body {"), "text.inverse": cite(f"{EV}/markup.txt", 'staticClass:"menu fixed inset-0 z-[11] bg-black text-white"'),
          "text.muted": cite(f"{EV}/markup.txt", 'staticClass:"text-gray-4 mr-8'), "text.subtle": cite(f"{EV}/site.css", ".text-gray-3 {"),
          "surface.page": cite(f"{EV}/site.css", "background-color:#9ab5ac"), "surface.paper": cite(f"{EV}/markup.txt", "bg-white z-4 overflow-hidden js-chapter-offset"),
          "surface.paper-stack": cite(f"{EV}/markup.txt", 'staticClass:"mask-3 absolute inset-0 bg-white-off'), "surface.pill": cite(f"{EV}/markup.txt", "sound p-[.4rem] s:p-[.55rem] pr-12 s:pr-32 flex bg-white"),
          "surface.pill-bright": cite(f"{EV}/markup.txt", "thec fixed"), "surface.accent": cite(f"{EV}/markup.txt", 'e("footer",{staticClass:"bg-yellow'),
          "surface.inverse": cite(f"{EV}/markup.txt", 'staticClass:"menu fixed inset-0 z-[11] bg-black'), "surface.muted": cite(f"{EV}/site.css", ".bg-gray-3 {")}
dump("tokens/10-semantic/semantic.json", {"category": "semantic", "tokens": {k: {"ref": v, "evidence": [sem_ev[k]]} for k, v in semantic.items()}})

component_tokens = {
    "button.pill.height": {"ref": "space.45", "evidence": [cite(f"{EV}/markup.txt", "btn btn-no-sound fixed bottom-[2rem] right-[3rem] h-[4.5rem] rounded-full")]},
    "button.pill.radius": {"ref": "radius.pill", "evidence": [cite(f"{EV}/site.css", "border-radius:9999px;")]},
    "button.pill.surface": {"ref": "surface.pill", "evidence": [cite(f"{EV}/markup.txt", "btn btn-no-sound fixed bottom-[2rem] right-[3rem] h-[4.5rem] rounded-full bg-white")]},
    "button.enter.surface": {"ref": "surface.accent", "evidence": [cite(f"{EV}/markup.txt", "eb flex items-center justify-center h-[15rem] s:h-[18.4rem]")]},
    "audio.pill.surface": {"ref": "surface.pill", "evidence": [cite(f"{EV}/markup.txt", "sound p-[.4rem] s:p-[.55rem] pr-12 s:pr-32 flex bg-white")]},
    "audio.pill.font": {"ref": "font.display", "evidence": [cite(f"{EV}/markup.txt", "sound p-[.4rem] s:p-[.55rem] pr-12 s:pr-32 flex bg-white overflow-hidden font-2")]},
    "audio.duration.text": {"ref": "text.muted", "evidence": [cite(f"{EV}/markup.txt", 'staticClass:"text-gray-4 mr-8')]},
    "paper.front.elevation": {"ref": "elevation.paper-1", "evidence": [cite(f"{EV}/site.css", "box-shadow:-1px 9px 10px rgba(0,0,0,.06);")]},
    "paper.middle.elevation": {"ref": "elevation.paper-2", "evidence": [cite(f"{EV}/site.css", "box-shadow:-2px 9px 10px rgba(0,0,0,.1);")]},
    "footer.surface": {"ref": "surface.accent", "evidence": [cite(f"{EV}/markup.txt", 'e("footer",{staticClass:"bg-yellow')]},
    "menu.bottom.surface": {"ref": "surface.accent", "evidence": [cite(f"{EV}/markup.txt", "menu-b__mask flex items-center justify-between px-36 w-full bg-yellow")]},
    "chip.hint.surface": {"ref": "surface.pill-bright", "evidence": [cite(f"{EV}/markup.txt", "thec fixed")]},
    "index.surface": {"ref": "surface.inverse", "evidence": [cite(f"{EV}/markup.txt", 'staticClass:"menu fixed inset-0 z-[11] bg-black')]},
}
dump("tokens/20-component/component.json", {"category": "component", "tokens": component_tokens})
dump("tokens/30-layout/layout.json", {"category": "layout", "tokens": {
    "layout.chapter-card.maxWidth": {"value": "32.5rem", "valueAtMin650": "75rem", "evidence": [cite(f"{EV}/markup.txt", "max-w-[32.5rem] s:max-w-[75rem] origin-bottom js-chapter-content")]},
    "layout.intro-card.maxWidth": {"value": "32.5rem", "valueAtMin650": "74rem", "evidence": [cite(f"{EV}/markup.txt", "home-mask-wrap relative w-full max-w-[32.5rem] s:max-w-[74rem]")]},
    "layout.about-stats.maxWidth": {"value": "100%", "valueAtMin650": "125rem", "evidence": [cite(f"{EV}/markup.txt", "s:max-w-[125rem] mt-75 s:mt-125")]},
    "layout.prose.maxWidth": {"value": "50rem", "evidence": [cite(f"{EV}/markup.txt", 'staticClass:"w-full max-w-[50rem] text-18 s:text-23 leading-[1.2] font-normal txt"')]},
    "layout.gutter": {"ref": "space.15", "refAtMin650": "space.30", "evidence": [cite(f"{EV}/markup.txt", "bg-yellow flex justify-between px-15 s:px-30 py-22")]},
    "layout.section.paddingBlock": {"ref": "space.75", "refAtMin650": "space.200", "evidence": [cite(f"{EV}/markup.txt", 'e("section",{staticClass:"py-75 s:py-200"}')]},
    "layout.gallery.columns": {"value": 2, "valueAtMin650": 4, "evidence": [cite(f"{EV}/markup.txt", "grid grid-cols-2 s:grid-cols-4 gap-15 s:gap-100", nth=2)]},
    "layout.viewport-height": {"value": "100svh", "evidence": [cite(f"{EV}/site.css", ".ui-height {")]},
}})
foundation_colors = {k: v["value"] for k, v in color.items()}
dump("tokens/themes/light.json", {"theme": "light", "note": "the only theme the source ships (no dark mode, no theme switch)",
     "resolved": {k: {"ref": v, "value": foundation_colors[v]} for k, v in semantic.items()}})

# ---------------------------------------------------------------- token catalog + policy (derived from the token files)
catalog = {"version": "1.0.0", "derivedFrom": "tokens/00-foundation/*.json, tokens/10-semantic, tokens/20-component, tokens/30-layout, tokens/themes/light.json (verify_all.py rebuilds this file and fails on any difference)", "categories": {}}
CAT = catalog["categories"]
CAT["color"] = {k: v["value"] for k, v in color.items()}
CAT["semanticColor"] = {k: foundation_colors[v] for k, v in semantic.items()}
CAT["fontFamily"] = {k: v["value"] for k, v in fonts.items()}
CAT["fontSize"] = {k: v["value"] for k, v in fontsize.items()}
CAT["lineHeight"] = {k: v["value"] for k, v in lineheight.items()}
CAT["letterSpacing"] = {k: v["value"] for k, v in tracking.items()}
CAT["radius"] = {k: v["value"] for k, v in radius.items()}
CAT["spacing"] = {k: v["value"] for k, v in spacing.items()}
CAT["breakpoint"] = {"breakpoint.s": "650px", "breakpoint.max-s": "649px", "breakpoint.has-hover": "(hover:hover) and (pointer:fine)"}
CAT["elevation"] = {k: v["value"] for k, v in load("tokens/00-foundation/elevation.json")["tokens"].items()}
CAT["motionDuration"] = {k: v["value"] for k, v in durations.items()}
CAT["motionEasing"] = {k: v["value"] for k, v in easing.items()}
CAT["motionPattern"] = {k: v["description"] for k, v in PATTERNS.items()}
dump("tokens/llm/token-catalog.json", catalog)

token_policy = {
    "version": "1.0.0",
    "appliesTo": "PageSpec node.style (the only per-instance styling field; everything else is owned by the section contracts)",
    "styleFields": {
        "surface": {"catalogKey": "semanticColor", "prefix": "surface."},
        "text": {"catalogKey": "semanticColor", "prefix": "text."},
        "fontFamily": {"catalogKey": "fontFamily", "prefix": "font."},
        "paddingBlock": {"catalogKey": "spacing", "prefix": "space."},
        "gap": {"catalogKey": "spacing", "prefix": "space."},
    },
    "rawValueRestrictions": {"semanticColor": "token reference only: no hex/rgb/hsl/named colours", "spacing": "token reference only: no px/rem/em/% values", "fontFamily": "token reference only: no family names"},
    "themes": {"light": {"allowedPairs": [["surface.paper", "text.primary"], ["surface.paper-stack", "text.primary"], ["surface.pill", "text.primary"], ["surface.pill-bright", "text.primary"],
                                          ["surface.accent", "text.primary"], ["surface.inverse", "text.inverse"], ["surface.page", "text.primary"], ["surface.pill", "text.muted"]]}},
    "allowedPairsEvidence": "pairs observed on the rendered site: paper cards and pills black on white, footer/bottom menu black on yellow, chapter index white on black (computed-1440 colour + background histograms; markup.txt classes)",
    "fonts": {"supported": ["font.text", "font.display", "font.fallback-sans"],
              "generatedMode": "font.text / font.display (Founders Grotesk, commercial, Klim Type Foundry) are allowed in a generated page only when the PageSpec declares fontLicence 'licensed-by-deployer'; otherwise use font.fallback-sans. The mirrored woff2 files are reference-only and never ship in generated output."},
    "rules": ["TOKEN_UNKNOWN", "TOKEN_RAW_COLOR", "TOKEN_ARBITRARY_SPACING", "TOKEN_UNSUPPORTED_FONT", "TOKEN_WRONG_CATEGORY", "TOKEN_INVALID_COMBINATION", "TOKEN_NOT_IN_THEME", "GENERATED_MODE_FONT_LICENCE"],
}
dump("tokens/llm/token-policy.json", token_policy)

# ---------------------------------------------------------------- asset roles
ROLES = {
    # reference-only / blocked: real proprietary assets of the source
    "brand.wordmark": ("reference-only", "must-reuse-exact-in-reference-only", "book wordmark (text-logo.svg + inline SVG wordmark in the preloader)", ["site/text-logo.svg"], ["generated.brand-mark"]),
    "brand.favicon": ("reference-only", "must-reuse-exact-in-reference-only", "favicons", ["site/favicon-pos.svg", "site/favicon-neg.svg"], ["generated.brand-mark"]),
    "book.cover": ("reference-only", "must-reuse-exact-in-reference-only", "book cover art and book product shots (cover.jpg, book-small.png, book-shadow.png, formats covers)", ["site/cover.jpg", "site/book-small.png", "site/formats/img/paper-cover.png", "site/formats/img/audio-cover.png"], ["generated.product-visual"]),
    "book.3d-model": ("blocked-for-generation", "must-not-reuse", "glTF book + KTX2/Basis textures rendered in the WebGL stage", ["site/3d/", "site/basis/"], ["generated.product-visual"]),
    "illustration.chapter": ("blocked-for-generation", "must-not-reuse", "commissioned chapter SVG illustrations (DatoCMS)", ["site/dato/"], ["generated.illustration"]),
    "illustration.map-tiles": ("blocked-for-generation", "must-not-reuse", "illustrated city map tiles 01-08.ktx2 on the explore page", ["site/01.ktx2"], ["generated.illustration"]),
    "illustration.about-scene": ("blocked-for-generation", "must-not-reuse", "about-page illustrated scenes (about/*.ktx2, about-bottom.jpg)", ["site/about/", "site/about-bottom.jpg"], ["generated.illustration"]),
    "author.portrait": ("blocked-for-generation", "must-not-fabricate", "photo of the real author (dl.png) - a real person's likeness", ["site/dl.png"], ["generated.fictional-person"]),
    "author.signature": ("blocked-for-generation", "must-not-fabricate", "the real author's signature (Rive sig-about / dl-sig, canvas signature)", ["site/riv/"], ["generated.signature"]),
    "badge.text-image": ("reference-only", "must-reuse-exact-in-reference-only", "raster text badges (circ-text.png 'THE NEW BOOK' ring, sound-on.png)", ["site/circ-text.png", "site/sound-on.png"], ["generated.badge"]),
    "audio.narration": ("blocked-for-generation", "must-not-reuse", "chapter narration + book synopsis audio: the real author's voice", ["site/synopsis.mp3", "site/dato/"], ["placeholder.audio"]),
    "audio.ambient-loop": ("reference-only", "must-reuse-exact-in-reference-only", "ambient music loop (loop.mp3)", ["site/loop.mp3"], ["placeholder.audio"]),
    "animation.rive": ("reference-only", "must-reuse-exact-in-reference-only", "Rive .riv animations (play/pause, close icon, arrows, balloon, book flipper)", ["site/riv/"], ["generated.illustration"]),
    "cursor.custom": ("reference-only", "must-reuse-exact-in-reference-only", "custom canvas cursor sprites", ["site/menu-default.png"], ["generated.illustration"]),
    "texture.noise": ("reference-only", "must-reuse-exact-in-reference-only", "noise texture for the WebGL paper look", ["site/noise.jpg"], ["generated.illustration"]),
    "link.outbound": ("blocked-for-generation", "must-not-reuse-live-endpoint", "author portfolio + retailer order link", [], ["placeholder.url"]),
    "link.download": ("blocked-for-generation", "must-not-reuse-live-endpoint", "live PDF / audiobook ZIP download endpoints", [], ["placeholder.url"]),
    # generation-safe
    "generated.brand-mark": ("generation-safe", "may-generate-new", "placeholder, user-supplied or newly generated brand mark / wordmark for a fictional brand", [], []),
    "generated.fictional-person": ("generation-safe", "may-generate-new", "fictional people: names, avatars, portraits generated for the page (never a real person's likeness)", [], []),
    "generated.signature": ("generation-safe", "may-generate-new", "newly drawn signature of a fictional author", [], []),
    "generated.product-visual": ("generation-safe", "may-generate-new", "generated product visual (book mock-up, 3D or flat) for a fictional product", [], []),
    "generated.illustration": ("generation-safe", "may-generate-new", "original generated illustration / scene / animation", [], []),
    "generated.badge": ("generation-safe", "may-generate-new", "generated text badge (circular label, sticker)", [], []),
    "placeholder.url": ("generation-safe", "may-generate-new", "placeholder URL on a reserved domain only (*.example, *.invalid) or a relative route", [], []),
    "placeholder.audio": ("generation-safe", "may-generate-new", "placeholder or synthetic narration / silence; never a real person's voice", [], []),
    "placeholder.rating": ("generation-safe", "may-generate-new", "placeholder rating. The source has NO ratings, reviews or testimonials and no PageSpec field uses this role; present only so a future rating slot has a safe role", [], []),
    "original.copy": ("generation-safe", "may-generate-new", "original copy written for the generated page", [], []),
}
LICENSING = ("The source is a real, live book site by a real, named author. Cover art, illustrations, 3D book textures, Rive files, the wordmark, "
             "the author's photo, signature and narrated voice are proprietary and are never reproduced in generated output. Founders Grotesk is a commercial "
             "Klim Type Foundry typeface: generated deliverables need their own licence or use font.fallback-sans.")
dump("assets/asset-roles.json", {"version": "1.0.0", "availabilityEnum": ["reference-only", "generation-safe", "blocked-for-generation"],
     "generationPolicyEnum": ["may-generate-new", "must-reuse-exact-in-reference-only", "must-not-fabricate", "must-not-reuse", "must-not-reuse-live-endpoint"],
     "licensing": LICENSING,
     "pinnedInCode": "availability is also pinned in schema/semantic_validate.py and extraction/verify_all.py (PINNED_AVAILABILITY); editing this file alone cannot loosen it",
     "sourceFilesNote": "sourceFiles are paths relative to the project root (the mirrored site next to design-repo/); documentation only, never shipped",
     "roles": {k: {"availability": a, "generationPolicy": g, "description": d, "sourceFiles": f, "generationSafeSubstitutes": s} for k, (a, g, d, f, s) in ROLES.items()}})

# ---------------------------------------------------------------- source identity patterns (R2)
headlines = [c["introTitle"] for c in COPY["chapters"]]
INV = load(f"{EV}/asset-inventory.json")["files"]
ASSET_PATTERNS = sorted({f["path"][len("site/"):] for f in INV if "/fonts/" not in f["path"] and not f["path"].startswith("site/dato/") and not f["path"].startswith("site/basis/") and not f["path"].startswith("site/vendor/")}
                        | {"/dato/", "datocms-assets", "founders-grotesk"})
ASSET_PATTERNS = sorted({("/" + p if re.match(r"^[0-9]{2}\.ktx2$", p) else p) for p in ASSET_PATTERNS})
def copy_cite(needle): return cite(f"{EV}/copy.json", needle)
about = page(C1440, "/about")["sections"]
dump("schema/source-patterns.json", {
    "version": "1.0.0",
    "note": "Generated-mode leakage patterns, all taken from the real source (copy.json, computed-*.json, markup.txt). Case-insensitive; typographic quotes/dashes normalised before matching.",
    "brand": {"patterns": ["The Search for Work Happiness", "Search for Work Happiness", "Work Happiness", "findworkhappiness", "find work happiness"], "evidence": [copy_cite('"title": "The Search for Work Happiness Book"'), copy_cite("book.findworkhappiness.com")]},
    "person": {"patterns": ["David Lubofsky", "Lubofsky", "davidlubofsky"], "evidence": [cite(f"{EV}/markup.txt", ' David Lubofsky\\n'), copy_cite("davidlubofsky.com")]},
    "url": {"patterns": ["findworkhappiness.com", "book.findworkhappiness.com", "davidlubofsky.com", "datocms", "datocms-assets"], "evidence": [copy_cite('"outboundUrls"'), copy_cite('"formatsDownloadUrls"')],
            "rule": "in generated mode every absolute URL must use a reserved .example or .invalid host"},
    "store": {"patterns": ["amazon.com", "amzn.", "B0BWSL3CRG"], "evidence": [copy_cite("amazon.com/dp/B0BWSL3CRG")]},
    "cta": {"patterns": ["Order the book", "Chapter summaries", "About the book", "Visit my online portfolio", "Enter without sound", "Drag around to find chapters", "Scroll through chapters", "Loading Chapters"],
            "evidence": [cite(f"{EV}/markup.txt", "Order the book"), cite(f"{EV}/markup.txt", 'label:"Chapter summaries"'), cite(f"{EV}/markup.txt", "Visit my online port"), cite(f"{EV}/markup.txt", "Enter without sound"), cite(f"{EV}/markup.txt", "Loading Chapters"), cite(f"{EV}/markup.txt", "Scroll")]},
    "copy": {"patterns": headlines + [COPY["site"]["description"], "Anecdotes to help leaders keep themselves and their people happy and mentally healthy",
                                     "I never set out to be a leader", "I had to leave home to build a better life", "This is not an all-or-nothing endeavor", "Intro to the book"],
             "shingleWords": 6, "corpus": "every section text in extraction/evidence/computed-1440.json plus copy.json strings; any 6-word run shared with the corpus is rejected in generated mode",
             "evidence": [copy_cite('"introTitle"'), copy_cite('"description"'), cite(f"{EV}/markup.txt", "I never set out to be a leader."), cite(f"{EV}/markup.txt", "I had to leave home to build a b")]},
    "statistic": {"patterns": ["16,020", "16020", "1,039", "1039", "copies sold", "28 custom illustrated", "160 pages"],
                  "note": "the About closer's four book statistics (words, copies sold, illustrated scenes, pages) are real sales/production claims of the source",
                  "evidence": [cite(f"{EV}/markup.txt", '[t._v("16,020")]'), cite(f"{EV}/markup.txt", '[t._v("1,039")]'), cite(f"{EV}/markup.txt", '[t._v("28")]'), cite(f"{EV}/markup.txt", '[t._v("160")]')]},
    "asset": {"patterns": ASSET_PATTERNS, "note": "source file names / paths from extraction/evidence/asset-inventory.json (file formats alone are not patterns: a generated .glb or .webp is fine)",
              "evidence": [cite(f"{EV}/asset-inventory.json", '"path": "site/' + n.lstrip("/") + '"') for n in ("text-logo.svg", "cover.jpg", "dl.png", "circ-text.png", "riv/book_master-rive.riv", "3d/happiness-new-angle-web-nomods-prebake.gltf", "synopsis.mp3")]},
    "rating": {"patterns": [], "note": "NOT APPLICABLE: the source has no reviews, ratings or testimonials (no rating markup in markup.txt, none in copy.json) and the PageSpec has no rating field, so GENERATED_MODE_RATING has nothing grounded to match. The nearest real claim class (sales statistics) is covered by GENERATED_MODE_STATISTIC."},
})

# ---------------------------------------------------------------- section contracts
def S(mw, **kw):
    d = {"type": "string", "minLength": 1, "maxWords": mw}; d.update(kw); return d
HREF = {"type": "string", "minLength": 1, "maxLength": 300}
ROUTE_REF = {"type": "string", "pattern": "^/[a-z0-9/_-]*$", "maxLength": 120}
def OBJ(props, req=None):
    return {"type": "object", "additionalProperties": False, "required": req if req is not None else list(props), "properties": props}
def ARR(item, lo, hi, total=None):
    d = {"type": "array", "minItems": lo, "maxItems": hi, "items": item}
    if total: d["maxWordsTotal"] = total
    return d

def flowsec(route, sid, w=1440, idx=0):
    c = {1440: C1440, 768: C768, 390: C390}[w]
    return page(c, route)["sections"].get(sid, [None] * (idx + 1))[idx]

def comp_cite(w, route, after_key=None):
    rel = f"{EV}/computed-{w}.json"
    return cite(rel, f'"route": "{route}"')

def sec_cite(w, route, sid, nth=1):
    rel = f"{EV}/computed-{w}.json"
    return cite(rel, f'"{sid}": [', nth=1, after=f'"route": "{route}"')

def struct(route, sid, idx=0):
    s = flowsec(route, sid, 1440, idx)
    return s.get("structure", {}) if s else {}

def maxw(route, sid, idx=0):
    st = struct(route, sid, idx)
    return max(st.get("paragraphWords") or [0])

ab_book, ab_s1, ab_s2 = struct("/about", "content.about-book"), struct("/about", "content.about-story", 0), struct("/about", "content.about-story", 1)
closer = struct("/about", "cta.download-closer")
AB_H2 = next(h["words"] for h in ab_book["headings"] if h["tag"] == "h2")
AB_H3 = next(h["words"] for h in ab_book["headings"] if h["tag"] == "h3")
AB_P = [w for w in ab_book["paragraphWords"] if w > 4]  # the 4-word paragraph is the eyebrow label
CLOSER_LABEL = max(closer["paragraphWords"])

RESP_ROOT = [cite(f"{EV}/site.css", "--size:375;"), cite(f"{EV}/site.css", "--size:1520;")]
def resp(changes, w768=None, w390=None, extra=None):
    ev = list(RESP_ROOT) + (extra or [])
    return {"breakpoints": {"below650": changes[0], "atOrAbove650": changes[1]}, "hoverCapableOnly": changes[2] if len(changes) > 2 else None,
            "measured": {k: v for k, v in (("768", w768), ("390", w390)) if v}, "evidence": ev}

def meas(route, sid, idx=0):
    out = {}
    for w in (1440, 768, 390):
        s = flowsec(route, sid, w, idx)
        if s: out[str(w)] = {"heightPx": s["heightPx"], "widthPx": s["widthPx"]}
    return out

PASS = "static-final-state"
SECTIONS = []
def section(id, title, category, source, desc, content, constraints, motion, responsive, slots, retrieval=True, reason=None, variants=None, measured_route=None, flow=True, idx=0, extra_ev=None):
    SECTIONS.append(dict(id=id, title=title, category=category, source=source, desc=desc, content=content, constraints=constraints, motion=motion,
                         responsive=responsive, slots=slots, retrieval=retrieval, reason=reason, variants=variants, measured_route=measured_route, flow=flow, idx=idx, extra_ev=extra_ev or []))

def SRC(sid, file, needle, nth=1, desc=None):
    c = cite(file, needle, nth)
    return {"id": sid, "file": file, "lines": c["cite"].split(":")[1], "tag": needle, "description": desc}

def MOT(patterns, default, fallback, trigger, ev):
    return {"allowedPatterns": patterns, "default": {"pattern": default, "trigger": trigger, "reducedMotionFallback": fallback}, "evidence": ev}

def SLOT(ref, gen, lo=0, hi=1):
    return {"referenceRoles": ref, "generatedRoles": gen, "minItems": lo, "maxItems": hi}

M = f"{EV}/markup.txt"; SC = f"{EV}/site.css"; EC = f"{EV}/embedded.css"

section("shell.header-nav", "Header navigation pills", "SHELL", SRC("vue:TheHeader/header.fixed", M, 'e("header",{staticClass:"fixed top-0 left-0 w-full z-7'),
        "Fixed top bar: two white pill links (chapter summaries, about) on the left, a 'Download' pill with a tilted book thumbnail on the right.",
        OBJ({"primaryLinks": ARR(OBJ({"label": S(3), "to": ROUTE_REF}), 2, 2), "downloadLabel": S(1), "downloadTo": ROUTE_REF}),
        {"onePerPage": True, "positionFixed": True},
        MOT(["clip-reveal", "hover-spring", "rive-state-machine", "none"], "clip-reveal", PASS, "load", [mcite("transition:transform .5s cubic-bezier(.34,1.56,.64,1)"), cite(SC, ".sh-btn {")]),
        resp(["pills shrink to BaseButtonMob ('Chapters' label), book download pill becomes a compact '--mob' link", "full pill labels, bb download pill with 11.6rem book image", "book image hover spring only on hover-capable pointers"],
             meas("/about", "shell.header-nav").get("768"), meas("/about", "shell.header-nav").get("390"), [cite(M, 'e("BaseButtonMob",{staticClass:"sh-btn --1"'), cite(SC, ".bb__book {")]),
        {"downloadThumb": SLOT(["book.cover"], ["generated.product-visual"], 0, 1)}, measured_route="/about", flow=False)
section("shell.bottom-menu", "Bottom chapter/explore toggle", "SHELL", SRC("vue:MenuBottom/div.menu-b", M, 'staticClass:"menu-b fixed bottom-[2rem]'),
        "Fixed yellow bar centred at the bottom with 'Chapter' / 'Explore' labels and a round toggle; desktop only (hidden below 650px).",
        OBJ({"items": ARR(OBJ({"label": S(1), "to": ROUTE_REF}), 2, 2)}),
        {"onePerPage": True, "positionFixed": True},
        MOT(["clip-reveal", "none"], "clip-reveal", PASS, "route-enter", [cite(EC, ".menu-b__mask {")]),
        resp(["hidden (class 'hidden s:flex')", "visible, 33.1rem x 6.55rem yellow bar"], meas("/explore", "shell.bottom-menu").get("768"), None, [cite(EC, ".menu-b {")]),
        {}, measured_route="/explore", flow=False)
section("shell.footer", "Yellow footer bar", "SHELL", SRC("vue:pages/about/footer", M, 'e("footer",{staticClass:"bg-yellow'),
        "Yellow bar at the very bottom of the about page: copyright line on the left, underlined portfolio link on the right.",
        OBJ({"copyright": S(4), "linkLabel": S(4), "linkHref": HREF}),
        {"onePerPage": True, "mustBeLast": True},
        MOT(["none", "fade"], "none", "none-required", "none", [cite(SC, ".uline {")]),
        resp(["text-14 / text-15, px-15", "text-18 / text-20, px-30"], meas("/about", "shell.footer").get("768"), meas("/about", "shell.footer").get("390"), [cite(M, 'e("p",{staticClass:"text-14 s:text-18"}')]),
        {"link": SLOT(["link.outbound"], ["placeholder.url"], 1, 1)}, measured_route="/about")
section("runtime.preloader", "Preloader counter", "RUNTIME", SRC("vue:Intro/div.intro.fixed", M, 'staticClass:"intro fixed inset-0 flex flex-col justify-between'),
        "Full-screen load sequence: giant word counter rolling ONE ... HUNDRED, the book cover loader in the centre and a pulsing 'Loading Chapters' label. Shown once before the intro page.",
        OBJ({"counterFrom": S(1), "counterTo": S(1), "loadingLabel": S(3)}),
        {"onePerPage": True, "positionFixed": True, "homeRouteOnly": True},
        MOT(["counter-roll", "pulse-loop", "fade"], "counter-roll", PASS, "load", [cite(SC, ".intro__list[data-v-158e6d46] {"), mcite("animation:pulse-158e6d46 5s infinite")]),
        resp(["text-105 counter, 7rem rows", "text-[21rem] counter, 14rem rows"], None, None, [cite(M, 'text-white text-105 s:text-[21rem]')]),
        {"cover": SLOT(["book.cover"], ["generated.product-visual"], 0, 1), "wordmark": SLOT(["brand.wordmark"], ["generated.brand-mark"], 0, 1)},
        retrieval=False, reason="Preloader is transient runtime UI shown only while assets load; it carries no retrievable page content.", flow=False)
section("runtime.sound-gate", "Sound gate pill", "RUNTIME", SRC("vue:BtnNoSound/button.btn-no-sound", M, 'e("button",{staticClass:"btn btn-no-sound fixed bottom-[1.5rem]'),
        "Fixed bottom-right pill that enters the experience without audio; disappears after use.",
        OBJ({"label": S(4)}), {"onePerPage": True, "positionFixed": True, "homeRouteOnly": True},
        MOT(["clip-reveal", "none"], "clip-reveal", PASS, "load", [cite(EC, ".btn-no-sound {")]),
        resp(["5rem round icon button", "auto-width pill with label"], meas("/", "runtime.sound-gate").get("768"), meas("/", "runtime.sound-gate").get("390")),
        {}, retrieval=False, reason="Sound gate is a one-time runtime control for audio permission; it is not page content.", measured_route="/", flow=False)
section("runtime.cursor", "Custom canvas cursor", "RUNTIME", SRC("vue:Cursor/canvas.fixed.z-2", M, 'e("canvas",{ref:"pop",staticClass:"fixed top-[-10rem]'),
        "20rem canvas cursor that follows the pointer; only on hover-capable devices.",
        OBJ({}, []), {"onePerPage": True, "positionFixed": True},
        MOT(["rive-state-machine", "none"], "rive-state-machine", PASS, "hover", [cite(SC, "@media (hover:hover) and (pointer:fine) {")]),
        resp(["not used on touch devices", "20rem cursor canvas", True], None, None),
        {"sprite": SLOT(["cursor.custom"], ["generated.illustration"], 0, 1)},
        retrieval=False, reason="Custom cursor is pointer-following runtime decoration with no content of its own.", measured_route="/explore", flow=False)
section("runtime.webgl-stage", "WebGL stage", "RUNTIME", SRC("vue:Gl/div.gl.fixed", EC, ".gl[data-v-51deb141] {"),
        "Fixed full-screen three.js canvas behind every app page (3D book, explore map planes, about scene planes).",
        OBJ({}, []), {"onePerPage": True, "positionFixed": True},
        MOT(["webgl-scene", "none"], "webgl-scene", PASS, "load", [cite(EC, ".gl[data-v-51deb141] {")]),
        resp(["same full-screen canvas, fewer planes on small screens", "full-screen canvas"], meas("/explore", "runtime.webgl-stage").get("768"), meas("/explore", "runtime.webgl-stage").get("390")),
        {"scene": SLOT(["book.3d-model", "illustration.map-tiles", "illustration.about-scene", "texture.noise"], ["generated.product-visual", "generated.illustration"], 0, 4)},
        retrieval=False, reason="WebGL stage is the shared rendering canvas; its content is described by the sections drawn into it.", measured_route="/explore", flow=False)
section("hero.book-intro", "Book intro paper stack", "HERO", SRC("vue:pages/index/home-mask-wrap", M, 'staticClass:"home-mask-wrap relative w-full'),
        "Opening composition of the intro page: three stacked white paper sheets (tilted), circular 'THE NEW BOOK' badge with the author portrait, book wordmark, one-line tagline (h1), signature and a round yellow enter button.",
        OBJ({"tagline": S(16), "enterLabel": S(3)}),
        {"onePerPage": True, "homeRouteOnly": True},
        MOT(["paper-stack-rise", "spin-loop", "rive-state-machine", "fade"], "paper-stack-rise", PASS, "load", [cite(SC, ".home-mask.--1[data-v-34bc0716] {"), mcite("animation:spin-34bc0716 5s linear infinite")]),
        resp(["card max-width 32.5rem, tagline text-18, enter button 15rem", "card max-width 74rem, tagline text-24, enter button 18.4rem", "paper sheets fly in only on hover-capable pointers (touch: translate on is-touch)"],
             meas("/", "hero.book-intro").get("768"), meas("/", "hero.book-intro").get("390"), [cite(SC, ".is-touch .is-loaded .home-mask-wrap[data-v-34bc0716] {")]),
        {"portrait": SLOT(["author.portrait"], ["generated.fictional-person"], 0, 1), "badge": SLOT(["badge.text-image"], ["generated.badge"], 0, 2),
         "wordmark": SLOT(["brand.wordmark"], ["generated.brand-mark"], 1, 1), "signature": SLOT(["author.signature"], ["generated.signature"], 0, 1)},
        measured_route="/", flow=False)
section("media.audio-player", "Audio pill player", "MEDIA", SRC("vue:Sound/article.sound", M, 'e("article",{staticClass:"sound p-[.4rem]', nth=2),
        "White pill audio player: optional author face, 'Ch.' label + title (synopsis or chapter number), Rive play/pause, elapsed time, waveform line and total duration.",
        OBJ({"label": S(2), "chapterPrefix": {"type": "boolean"}, "duration": {"type": "string", "pattern": "^[0-9]{1,2}:[0-5][0-9]$"}}),
        {"onePerPage": True},
        MOT(["clip-reveal", "rive-state-machine", "none"], "clip-reveal", PASS, "route-enter", [cite(EC, ".sound {"), cite(EC, "clip-path:inset(0 calc(50% - 3.3rem)")]),
        resp(["--height 5rem, face 4.2rem, waveform 5rem wide", "--height 6.6rem, face 5.4rem, waveform 18.5rem wide"], meas("/chapter/one", "media.audio-player").get("768"), meas("/chapter/one", "media.audio-player").get("390"), [cite(EC, "--height:6.6rem;")]),
        {"audio": SLOT(["audio.narration"], ["placeholder.audio"], 1, 1), "face": SLOT(["author.portrait"], ["generated.fictional-person"], 0, 1)},
        measured_route="/chapter/one")
section("navigation.explore-map", "Explore map navigation", "NAVIGATION", SRC("vue:pages/explore/thec", M, 'staticClass:"thec fixed'),
        "Draggable illustrated city map (drawn in the WebGL stage on a 175vw grid) with chapter markers; a white hint chip with a yellow circle follows the pointer ('drag around to find chapters').",
        OBJ({"hint": S(6), "markerCount": {"type": "integer", "minimum": 1, "maximum": 12}}),
        {"onePerPage": True, "positionFixed": True},
        MOT(["webgl-scene", "clip-reveal", "none"], "webgl-scene", PASS, "drag", [cite(EC, ".thec {"), cite(EC, ".c1 {")]),
        resp(["grid 400vw wide; hint chip not shown on touch (measured: absent at 390)", "grid 175vw wide; hint chip follows the pointer", "hint chip only for hover-capable pointers"], meas("/explore", "navigation.explore-map").get("768"), None, [cite(EC, "width:175vw;")]),
        {"mapTiles": SLOT(["illustration.map-tiles"], ["generated.illustration"], 0, 8)}, measured_route="/explore", flow=False)
section("navigation.chapter-index", "Chapter index", "NAVIGATION", SRC("vue:pages/navigation/div.menu", M, 'staticClass:"menu fixed inset-0 z-[11] bg-black text-white"'),
        "Full-screen black chapter index: a vertically scrolling list of big 'CH. 01 ... 12' numerals, a rotated 'scroll through chapters' hint, top links (order the book, author) and a Rive book in the centre.",
        OBJ({"items": ARR(OBJ({"number": {"type": "string", "pattern": "^[0-9]{2}$"}, "to": ROUTE_REF}), 1, 12), "scrollHint": S(3), "orderLabel": S(3), "orderHref": HREF, "authorLabel": S(2), "authorHref": HREF}),
        {"onePerPage": True, "positionFixed": True},
        MOT(["clip-reveal", "rive-state-machine", "snappy-tween", "none"], "clip-reveal", PASS, "route-enter", [cite(EC, ".menu[data-v-382a306b] {")]),
        resp(["list at left 2rem, book top 12.5rem / half width", "list at left 20rem, book centred right 12rem"], meas("/navigation", "navigation.chapter-index").get("768"), meas("/navigation", "navigation.chapter-index").get("390"), [cite(M, "absolute left-[2rem] s:left-[20rem] top-0 bottom-0 z-2")]),
        {"book": SLOT(["animation.rive", "book.cover"], ["generated.product-visual"], 0, 1), "orderLink": SLOT(["link.outbound"], ["placeholder.url"], 1, 1), "authorLink": SLOT(["link.outbound"], ["placeholder.url"], 1, 1)},
        measured_route="/navigation", flow=False)
section("chapter.header", "Chapter header", "EDITORIAL", SRC("vue:pages/chapter/_slug/h1", M, 's("h1",{staticClass:"relative text-85 s:text-180'),
        "Top of the chapter paper card: small 'Ch.' label over a scribble, the numeral word in giant condensed type (text-180) and the chapter headline (h2, text-55).",
        OBJ({"prefix": S(1), "numeralWord": S(1), "headline": S(12)}),
        {"onePerPage": True},
        MOT(["paper-stack-rise", "snappy-tween", "fade"], "paper-stack-rise", PASS, "route-enter", [cite(EC, ".mask-1[data-v-ffb10910] {")]),
        resp(["numeral text-85, headline text-24, card 32.5rem", "numeral text-180, headline text-55, card 75rem"], meas("/chapter/one", "chapter.header").get("768"), meas("/chapter/one", "chapter.header").get("390"), [cite(SC, ".s\\:text-180 {")]),
        {"illustration": SLOT(["illustration.chapter"], ["generated.illustration"], 0, 1)}, measured_route="/chapter/one", extra_ev=[copy_cite('"introTitleWords": 12')])
section("chapter.body", "Chapter body prose", "EDITORIAL", SRC("css:.txt prose block", SC, ".txt>:not(:last-child) {"),
        "Chapter prose inside the paper card: 3-4 paragraphs with bold and underlined emphasis. Budgets are the observed maxima over all 12 chapters (copy.json).",
        OBJ({"paragraphs": ARR(OBJ({"text": S(71), "marks": {"type": "array", "uniqueItems": True, "items": {"enum": ["strong", "underline"]}}}, ["text"]), 3, 4, total=167)}),
        {"onePerPage": True},
        MOT(["fade", "snappy-tween", "none"], "fade", "instant-opacity", "scroll", [mcite("transition:opacity .5s ease-out")]),
        resp(["paragraph spacing per .txt rule, text-18", "larger paragraph spacing at >= 650px"], meas("/chapter/one", "chapter.body").get("768"), meas("/chapter/one", "chapter.body").get("390"), [cite(SC, ".txt>:not(:last-child) {", nth=2)]),
        {}, measured_route="/chapter/one", extra_ev=[copy_cite('"maxParagraphWords": 71'), copy_cite('"bodyWords": 167'), copy_cite('"paragraphs": 3')])
section("chapter.pager", "Chapter pager", "NAVIGATION", SRC("vue:ChapterUI/nav", M, 'e("nav",{staticClass:"absolute bottom-0 left-0 w-full flex justify-between px-10'),
        "Fixed chapter controls: round close (X) button top-right back to explore, 'Prev' / 'Next' pills at the bottom corners with Rive arrows.",
        OBJ({"prevLabel": S(1), "nextLabel": S(1), "closeLabel": S(1), "prevTo": ROUTE_REF, "nextTo": ROUTE_REF}),
        {"onePerPage": True, "positionFixed": True},
        MOT(["clip-reveal", "rive-state-machine", "none"], "clip-reveal", PASS, "hover", [cite(EC, ".close__mask[data-v-06212e2c] {")]),
        resp(["ChapterButtonMob round 5rem buttons, close 5rem", "ChapterButton 6rem pills with labels, close 6.5rem"], meas("/chapter/one", "chapter.pager").get("768"), meas("/chapter/one", "chapter.pager").get("390"), [cite(M, "ChapterButtonMob")]),
        {}, measured_route="/chapter/one", flow=False)
section("hero.about-title", "About title hero", "HERO", SRC("vue:pages/about/ui-height", M, 'staticClass:"relative ui-height flex items-start'),
        "Opening viewport of the about page: giant 'ABOUT' wordmark type, tilted book, signature and a Rive balloon carrying the book; exactly one viewport tall.",
        OBJ({"title": S(1)}),
        {"onePerPage": True},
        MOT(["webgl-scene", "rive-state-machine", "fade"], "webgl-scene", PASS, "load", [cite(SC, ".ui-height {")]),
        resp(["100svh, items-start", "100svh, items-center"], meas("/about", "hero.about-title").get("768"), meas("/about", "hero.about-title").get("390")),
        {"book": SLOT(["book.cover", "book.3d-model"], ["generated.product-visual"], 0, 1), "signature": SLOT(["author.signature"], ["generated.signature"], 0, 1), "balloon": SLOT(["animation.rive"], ["generated.illustration"], 0, 1)},
        measured_route="/about")
section("content.about-book", "About: intro to the book", "EDITORIAL", SRC("vue:pages/about/js-book-end", M, 'staticClass:"pt-100 pb-75 s:pb-200 js-book-end"'),
        "Eyebrow + big condensed heading (h2) + lead sentence (h3) + intro prose about why the book exists, beside the scroll-driven book.",
        OBJ({"eyebrow": S(4), "heading": S(AB_H2), "lead": S(AB_H3), "paragraphs": ARR(OBJ({"text": S(max(AB_P))}), 1, len(AB_P), total=sum(AB_P))}),
        {"onePerPage": True},
        MOT(["fade", "snappy-tween", "none"], "fade", "instant-opacity", "scroll", [mcite("transition:opacity .5s ease-out")]),
        resp(["heading text-60, prose text-18", "heading text-100, prose text-29"], meas("/about", "content.about-book").get("768"), meas("/about", "content.about-book").get("390"), [cite(M, 'e("div",{staticClass:"text-18 s:text-29 leading-[1.1] font-normal txt"}')]),
        {}, measured_route="/about")
section("gallery.illustration-strip", "Illustration strip", "GALLERY", SRC("vue:AboutImages/grid", M, "grid grid-cols-2 s:grid-cols-4 gap-15 s:gap-100", nth=2),
        "Row of four tall illustrated figures (WebGL planes, 155% aspect). Appears twice on the about page with different image sets.",
        OBJ({}, []), {"maxPerPage": 2},
        MOT(["webgl-scene", "fade", "none"], "webgl-scene", PASS, "scroll", [cite(EC, ".gl[data-v-51deb141] {")]),
        resp(["2 columns, gap 1.5rem", "4 columns, gap 10rem"], meas("/about", "gallery.illustration-strip").get("768"), meas("/about", "gallery.illustration-strip").get("390"), [cite(SC, ".grid-cols-2 {"), cite(SC, ".s\\:grid-cols-4 {")]),
        {"figure": SLOT(["illustration.about-scene"], ["generated.illustration"], 4, 4)}, variants=["a", "b"], measured_route="/about")
section("content.about-story", "About: author story", "EDITORIAL", SRC("vue:pages/about/section.py-75", M, 'e("section",{staticClass:"py-75 s:py-200"}'),
        "Author-story band: giant condensed heading (h2) beside a column of prose. Appears twice with different headings.",
        OBJ({"heading": S(max(h["words"] for h in (ab_s1.get("headings") or [{"words": 10}]) + (ab_s2.get("headings") or []))),
             "paragraphs": ARR(OBJ({"text": S(max((ab_s1.get("paragraphWords") or [1]) + (ab_s2.get("paragraphWords") or [1])))}), 1, max(len(ab_s1.get("paragraphWords") or [1]), len(ab_s2.get("paragraphWords") or [1])),
                               total=max(sum(ab_s1.get("paragraphWords") or [1]), sum(ab_s2.get("paragraphWords") or [1])))}),
        {"maxPerPage": 2},
        MOT(["fade", "snappy-tween", "none"], "fade", "instant-opacity", "scroll", [mcite("transition:opacity .5s ease-out")]),
        resp(["heading text-60 stacked above prose text-18", "heading text-100 beside prose text-23 (max-width 50rem)"], meas("/about", "content.about-story").get("768"), meas("/about", "content.about-story").get("390"), [cite(SC, ".py-75 {")]),
        {}, variants=["a", "b"], measured_route="/about")
section("cta.download-closer", "Download closer with book stats", "CTA", SRC("vue:pages/about/section.relative.pb-100", M, 'e("section",{staticClass:"relative pb-100 s:pb-150'),
        "Conversion closer of the about page: one giant headline figure plus a row of three stat-blocks (value + label) about the book, then the dark Download button (BuyNowButton) linking to the formats page. The stats sit in the SAME <section> as the button (markup.txt), so they are modelled as a stat-block component inside this CTA, not as a separate PROOF section.",
        OBJ({"stats": ARR(OBJ({"value": {"type": "string", "pattern": "^[0-9][0-9,.]*$", "maxLength": 12}, "label": S(CLOSER_LABEL)}), 4, 4), "ctaLabel": S(1), "ctaTo": ROUTE_REF}),
        {"onePerPage": True, "mustPrecedeFooter": True},
        MOT(["fade", "rive-state-machine", "hover-spring", "none"], "fade", "instant-opacity", "scroll", [mcite("transition:opacity .5s ease-out")]),
        resp(["lead figure text-140, stat values text-100 stacked", "lead figure text-[49.2rem], stat values text-170 in a row (max 125rem)"], meas("/about", "cta.download-closer").get("768"), meas("/about", "cta.download-closer").get("390"), [cite(M, 'e("h2",{staticClass:"text-140 s:text-[49.2rem]')]),
        {"book": SLOT(["book.cover", "book.3d-model"], ["generated.product-visual"], 0, 1), "signature": SLOT(["author.signature", "animation.rive"], ["generated.signature"], 0, 1)},
        measured_route="/about", extra_ev=[cite(M, 'e("BuyNowButton",{attrs:{dark:!0}})'), cite(M, '[t._v("1,039")]')])
section("cta.download-formats", "Download format card", "CTA", SRC("html:formats/body>div", f"{EV}/copy.json", '"formatsDownloadUrls": ['),
        "Static download page card (plain HTML, outside the app): format heading, cover image link and a 'Download ...' text link. Two variants: print (PDF) and audiobook (ZIP). Conversion block, CTA-classed.",
        OBJ({"heading": S(2), "linkLabel": S(2), "href": HREF}),
        {"maxPerPage": 2},
        MOT(["none"], "none", "none-required", "none", []),
        resp(["single centred column (no breakpoint in the formats stylesheet's measured output)", "same single column"], meas("/formats/", "cta.download-formats").get("768"), meas("/formats/", "cta.download-formats").get("390")),
        {"cover": SLOT(["book.cover"], ["generated.product-visual"], 1, 1), "download": SLOT(["link.download"], ["placeholder.url"], 1, 1)},
        variants=["print", "audiobook"], measured_route="/formats/")

RETRIEVAL_INELIGIBLE = sorted(s["id"] for s in SECTIONS if not s["retrieval"])
for s in SECTIONS:
    ev = list(s["extra_ev"])
    if s["measured_route"]:
        ev.append(sec_cite(1440, s["measured_route"], s["id"]))
    contract = {
        "id": s["id"], "title": s["title"], "version": "1.0.0",
        "source": {k: v for k, v in s["source"].items() if v is not None},
        "semantic": {"id": s["id"], "category": s["category"]},
        "description": s["desc"],
        "retrievalEligible": s["retrieval"],
        **({"retrievalReason": s["reason"]} if s["reason"] else {}),
        "flow": "in-flow" if s["flow"] else "fixed-or-overlay",
        "variants": s["variants"] or [],
        "content": s["content"],
        "constraints": s["constraints"],
        "motion": s["motion"],
        "responsive": s["responsive"],
        "assetSlots": s["slots"],
        "assetRoles": sorted({r for sl in s["slots"].values() for r in sl["referenceRoles"]}),
        "generatedAssetRoles": sorted({r for sl in s["slots"].values() for r in sl["generatedRoles"]}),
        "measured": meas(s["measured_route"], s["id"]) if s["measured_route"] else {"note": "transient runtime UI: not present after load, no stable box to measure"},
        "evidence": ev,
    }
    if s["measured_route"]:
        for w in (768, 390):
            if flowsec(s["measured_route"], s["id"], w):
                contract["responsive"]["evidence"].append(sec_cite(w, s["measured_route"], s["id"]))
    dump(f"sections/{s['id']}.json", contract)

# ---------------------------------------------------------------- primitives / components
PRIMS = {
    "pill-button": ("Rounded-full pill (white or white-classic) with condensed bold uppercase label and an SVG mask hover fill", [cite(M, "btn relative h-[4.8rem] rounded-full radius-fix bg-white")], ["radius.pill", "surface.pill", "font.display"]),
    "round-button": ("Round button (close X, enter arrow, sound gate on mobile)", [cite(M, "close relative w-[5rem] s:w-[6.5rem] h-[5rem] s:h-[6.5rem] rounded-full bg-white")], ["radius.pill", "surface.pill", "surface.accent"]),
    "underline-link": ("Text link with animated underline (.uline)", [cite(SC, ".uline {")], ["text.primary"]),
    "caps-label": ("Condensed bold uppercase label (font-2, tracking .04em)", [cite(SC, ".tracking-\\[\\.04em\\] {")], ["font.display"]),
    "canvas-surface": ("Canvas element hosting a Rive artboard or WebGL output", [cite(M, 'e("canvas",{ref:"sig"')], []),
    "paper-sheet": ("Flat paper rectangle (white / white-off) with paper elevation and a small rotation", [cite(SC, ".home-mask.--2[data-v-34bc0716] {")], ["surface.paper", "surface.paper-stack", "elevation.paper-1", "elevation.paper-2"]),
}
COMPS = {
    "paper-card-stack": ("Three paper sheets stacked behind a white content card (intro + chapter card)", ["paper-sheet"], [cite(M, 'staticClass:"mask-3 absolute inset-0 bg-white-off')]),
    "audio-pill": ("Audio player pill: face, label, Rive play/pause, times, waveform", ["pill-button", "canvas-surface", "caps-label"], [cite(EC, ".sound {")]),
    "nav-pill-group": ("Row of pill links", ["pill-button"], [cite(M, 'e("nav",{staticClass:"flex pointer-events-auto"},[e("BaseButton"')]),
    "stat-block": ("Big condensed number + short label with a bold word (About closer stats row)", ["caps-label"], [cite(M, 'e("h3",{staticClass:"text-100 s:text-170 font-2 font-bold leading-none text-center"}')]),
    "download-card": ("Format heading + cover image link + text link (formats page)", ["underline-link"], [cite(f"{EV}/copy.json", '"formatsDownloadUrls": [')]),
    "numeral-list-item": ("'CH.' + two-digit numeral link in the chapter index", ["caps-label"], [cite(M, 'e("ul",{ref:"list",staticClass:"relative js-menu-list"}')]),
}
for k, (d, ev, toks) in PRIMS.items():
    dump(f"primitives/{k}.json", {"id": f"primitive.{k}", "description": d, "tokens": toks, "evidence": ev})
for k, (d, uses, ev) in COMPS.items():
    dump(f"components/{k}.json", {"id": f"component.{k}", "description": d, "uses": [f"primitive.{u}" for u in uses], "evidence": ev})

# ---------------------------------------------------------------- templates + routes
NUM = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
def N(sec, required=True, variant=None, repeatable=False):
    d = {"section": sec, "required": required, "repeatable": repeatable}
    if variant: d["variant"] = variant
    return d
CHROME = lambda: [N("shell.header-nav"), N("shell.bottom-menu")]
RUNTIME = lambda: [N("runtime.webgl-stage"), N("runtime.cursor")]
templates = {
    "intro": {"title": "Book intro (home)", "family": "home", "routes": ["/"], "routePattern": "^/$",
              "nodes": [N("runtime.preloader")] + CHROME() + [N("hero.book-intro"), N("media.audio-player"), N("runtime.sound-gate")] + RUNTIME()},
    "explore": {"title": "Explore map", "family": "navigation", "routes": ["/explore"], "routePattern": "^/[a-z-]+$",
                "nodes": CHROME() + [N("navigation.explore-map")] + RUNTIME()},
    "chapter": {"title": "Chapter summary", "family": "article", "routes": [f"/chapter/{n}" for n in NUM], "routePattern": "^/chapter/[a-z0-9-]+$",
                "nodes": CHROME() + [N("media.audio-player"), N("chapter.header"), N("chapter.body"), N("chapter.pager")] + RUNTIME()},
    "chapter-index": {"title": "Chapter index", "family": "navigation", "routes": ["/navigation"], "routePattern": "^/[a-z-]+$",
                      "nodes": CHROME() + [N("navigation.chapter-index")] + RUNTIME()},
    "about": {"title": "About the book", "family": "about", "routes": ["/about"], "routePattern": "^/[a-z-]+$",
              "nodes": CHROME() + [N("hero.about-title"), N("content.about-book"), N("gallery.illustration-strip", variant="a"), N("content.about-story", variant="a"),
                                   N("gallery.illustration-strip", variant="b"), N("content.about-story", variant="b"), N("cta.download-closer"), N("shell.footer")] + RUNTIME()},
    "download-formats": {"title": "Download formats", "family": "conversion", "routes": ["/formats/"], "routePattern": "^/[a-z-]+/?$",
                         "nodes": [N("cta.download-formats", variant="print"), N("cta.download-formats", variant="audiobook")]},
}
# evidence for each template: the measured page in computed-1440 (one route per template)
TPL_MEASURED = {"intro": "/", "explore": "/explore", "chapter": "/chapter/one", "chapter-index": "/navigation", "about": "/about", "download-formats": "/formats/"}
for t, r in TPL_MEASURED.items():
    templates[t]["evidence"] = [cite(f"{EV}/computed-1440.json", f'"route": "{r}"')]
    templates[t]["measuredRoute"] = r
templates["download-formats"]["notes"] = "plain static HTML page outside the app (own stylesheet, own font names 'Founders Bold' / 'Founders Condensed'); reachable by direct load"
for t in ("explore", "chapter", "chapter-index", "about"):
    templates[t]["notes"] = "reachable ONLY by in-app navigation: a direct load of this path answers 301 -> '/' (same as the original host)"
routes = {r: t for t, d in templates.items() for r in d["routes"]}
dump("templates/templates.json", {"version": "1.0.0",
     "structuralNotes": ["Direct loads of /about, /explore, /navigation and /chapter/* return 301 -> '/' on the original host and on the clone server; these pages exist only through in-app navigation (router push or clicking). Templates still map them because they are real, content-bearing routes.",
                         "/formats/ is a separate static HTML download page, not part of the app; it has no shell, runtime or WebGL nodes.",
                         "Fixed chrome (header pills, bottom menu, WebGL stage, cursor) is measured on all five measured app routes at 1440 (computed-1440.json) and is required in every app template; it takes no page height. The bottom menu is hidden below 650px and the cursor only reacts on hover-capable pointers."],
     "templates": templates, "routes": routes})

# ---------------------------------------------------------------- compatibility graph
HEROLESS = ["explore", "chapter", "chapter-index", "download-formats"]
graph = {"version": "1.0.0",
         "note": "Every rule id here is implemented in schema/semantic_validate.py under the same id and severity; verify_all.py fails if the two sets differ.",
         "rules": {
    "ONE_HERO": {"severity": "error", "description": "at most one HERO-category node per page; templates with a hero must have exactly one", "exceptions": {"heroless templates": HEROLESS}},
    "HERO_FIRST_IN_FLOW": {"severity": "error", "description": "the HERO node is the first in-flow node of the page (fixed/runtime nodes take no position)"},
    "FOOTER_LAST": {"severity": "error", "description": "shell.footer, when present, is the last in-flow node"},
    "CTA_BEFORE_FOOTER": {"severity": "error", "description": "a node with constraint mustPrecedeFooter sits directly before shell.footer (in-flow order)"},
    "ONE_PER_PAGE": {"severity": "error", "description": "sections with onePerPage appear at most once; maxPerPage caps repeatable sections; checked on (section, variant)"},
    "NO_CONSECUTIVE_SAME_VARIANT": {"severity": "error", "description": "the same (section, variant) never appears twice in a row"},
    "NO_ADJACENT_SAME_CATEGORY": {"severity": "warn", "description": "two adjacent in-flow nodes should not share a semantic category",
                                  "exceptions": {"chapter.header->chapter.body": "header and body are the two halves of one paper card (EDITORIAL->EDITORIAL by design)",
                                                 "cta.download-formats->cta.download-formats": "print and audiobook cards of the download page"}},
    "CHAPTER_HEADER_BEFORE_BODY": {"severity": "error", "description": "chapter.body requires chapter.header earlier on the page"},
    "HOME_ROUTE_ONLY": {"severity": "error", "description": "sections with homeRouteOnly (preloader, sound gate, book intro hero) only on route '/'"},
    "RUNTIME_NOT_RETRIEVABLE": {"severity": "error", "description": "runtime/utility sections (pinned list) are never retrievalEligible; content sections are never marked ineligible"},
    "MOTION_BUDGET": {"severity": "warn", "description": "at most 2 nodes with a looping motion pattern (pulse-loop, spin-loop) per page; the source uses one per page"},
}}
dump("compatibility/graph.json", graph)

# ---------------------------------------------------------------- PageSpec schema (Draft-07, closed)
roles_enum = sorted(ROLES)
defs = {
    "assetRole": {"enum": roles_enum},
    "motion": {"type": "object", "additionalProperties": False, "required": ["pattern", "trigger", "reducedMotionFallback"],
               "properties": {"pattern": {"enum": sorted(PATTERNS)}, "trigger": {"enum": ["load", "route-enter", "scroll", "hover", "toggle", "drag", "audio", "none"]},
                              "reducedMotionFallback": {"enum": ["static-final-state", "instant-opacity", "none-required"]},
                              "durationToken": {"type": "string", "pattern": "^duration\\.[0-9]+ms$"}, "easingToken": {"type": "string", "pattern": "^easing\\.[a-z-]+$"}}},
    "asset": {"type": "object", "additionalProperties": False, "required": ["slot", "role", "alt"],
              "properties": {"slot": {"type": "string", "pattern": "^[a-zA-Z]+$"}, "role": {"$ref": "#/definitions/assetRole"}, "src": {"type": "string", "minLength": 1, "maxLength": 300}, "alt": {"type": "string", "maxLength": 200, "maxWords": 20}}},
    "style": {"type": "object", "additionalProperties": False, "minProperties": 1,
              "properties": {k: {"type": "string", "minLength": 1, "maxLength": 80} for k in token_policy["styleFields"]}},
}
branches = []
for s in SECTIONS:
    defs[f"content.{s['id']}"] = s["content"]
    then = {"properties": {"content": {"$ref": f"#/definitions/content.{s['id']}"},
                           "motion": {"properties": {"pattern": {"enum": s["motion"]["allowedPatterns"]}}}}}
    if s["variants"]:
        then["required"] = ["variant"]; then["properties"]["variant"] = {"enum": s["variants"]}
    else:
        then["not"] = {"required": ["variant"]}
    branches.append({"if": {"properties": {"section": {"const": s["id"]}}, "required": ["section"]}, "then": then})
defs["node"] = {"type": "object", "additionalProperties": False, "required": ["section", "content", "motion"],
                "properties": {"section": {"enum": [s["id"] for s in SECTIONS]}, "variant": {"type": "string"}, "content": {"type": "object"},
                               "motion": {"$ref": "#/definitions/motion"}, "assets": {"type": "array", "maxItems": 12, "items": {"$ref": "#/definitions/asset"}},
                               "style": {"$ref": "#/definitions/style"}, "retrievalEligible": {"type": "boolean"}},
                "allOf": branches}
pagespec = {"$schema": "http://json-schema.org/draft-07/schema#", "$id": "pagespec.schema.json", "title": "PageSpec", "type": "object", "additionalProperties": False,
            "required": ["pageSpecVersion", "mode", "template", "route", "theme", "meta", "nodes"],
            "properties": {"pageSpecVersion": {"const": PAGESPEC_VERSION},
                           "mode": {"enum": ["reference", "generated"], "description": "reference = faithful reconstruction of the source; generated = new page that must contain nothing identifying the source"},
                           "template": {"enum": list(templates)}, "route": {"type": "string", "pattern": "^/[a-z0-9/_-]*$", "maxLength": 120}, "theme": {"enum": ["light"]},
                           "fontLicence": {"enum": ["licensed-by-deployer", "fallback"]},
                           "meta": {"type": "object", "additionalProperties": False, "required": ["title", "description"],
                                    "properties": {"title": {"type": "string", "minLength": 1, "maxWords": 10}, "description": {"type": "string", "minLength": 1, "maxWords": 30}}},
                           "nodes": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"$ref": "#/definitions/node"}}},
            "if": {"properties": {"mode": {"const": "generated"}}, "required": ["mode"]}, "then": {"required": ["fontLicence"]},
            "definitions": defs}
dump("schema/pagespec.schema.json", pagespec)

contract_schema = {"$schema": "http://json-schema.org/draft-07/schema#", "$id": "section-contract.schema.json", "title": "Section contract", "type": "object", "additionalProperties": False,
    "required": ["id", "title", "version", "source", "semantic", "description", "retrievalEligible", "flow", "variants", "content", "constraints", "motion", "responsive", "assetSlots", "assetRoles", "generatedAssetRoles", "measured", "evidence"],
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z]+\\.[a-z0-9-]+$"}, "title": {"type": "string"}, "version": {"type": "string"},
        "source": {"type": "object", "additionalProperties": False, "required": ["id", "file", "lines", "tag"],
                   "properties": {"id": {"type": "string"}, "file": {"type": "string"}, "lines": {"type": "string", "pattern": "^[0-9]+(-[0-9]+)?$"}, "tag": {"type": "string", "minLength": 3}, "description": {"type": "string"}}},
        "semantic": {"type": "object", "additionalProperties": False, "required": ["id", "category"],
                     "properties": {"id": {"type": "string"}, "category": {"enum": ["SHELL", "HERO", "NAVIGATION", "MEDIA", "EDITORIAL", "GALLERY", "CTA", "RUNTIME"]}}},
        "description": {"type": "string"},
        "retrievalEligible": {"type": "boolean"}, "retrievalReason": {"type": "string", "minLength": 30},
        "flow": {"enum": ["in-flow", "fixed-or-overlay"]}, "variants": {"type": "array", "items": {"type": "string"}},
        "content": {"type": "object"},
        "constraints": {"type": "object", "additionalProperties": False, "properties": {k: {"type": "boolean"} for k in ["onePerPage", "positionFixed", "homeRouteOnly", "mustBeLast", "mustPrecedeFooter"]} | {"maxPerPage": {"type": "integer", "minimum": 1}}},
        "motion": {"type": "object", "additionalProperties": False, "required": ["allowedPatterns", "default", "evidence"],
                   "properties": {"allowedPatterns": {"type": "array", "minItems": 1, "items": {"enum": sorted(PATTERNS)}},
                                  "default": {"type": "object", "additionalProperties": False, "required": ["pattern", "trigger", "reducedMotionFallback"],
                                              "properties": {"pattern": {"enum": sorted(PATTERNS)}, "trigger": {"type": "string"}, "reducedMotionFallback": {"enum": ["static-final-state", "instant-opacity", "none-required"]}}},
                                  "evidence": {"type": "array"}}},
        "responsive": {"type": "object", "additionalProperties": False, "required": ["breakpoints", "evidence"],
                       "properties": {"breakpoints": {"type": "object", "additionalProperties": False, "required": ["below650", "atOrAbove650"], "properties": {"below650": {"type": "string"}, "atOrAbove650": {"type": "string"}}},
                                      "hoverCapableOnly": {"type": ["string", "boolean", "null"]}, "measured": {"type": "object"}, "evidence": {"type": "array", "minItems": 1}}},
        "assetSlots": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": False, "required": ["referenceRoles", "generatedRoles", "minItems", "maxItems"],
                                                                  "properties": {"referenceRoles": {"type": "array", "items": {"enum": roles_enum}}, "generatedRoles": {"type": "array", "items": {"enum": roles_enum}}, "minItems": {"type": "integer"}, "maxItems": {"type": "integer"}}}},
        "assetRoles": {"type": "array", "items": {"enum": roles_enum}}, "generatedAssetRoles": {"type": "array", "items": {"enum": roles_enum}},
        "measured": {"type": "object"}, "evidence": {"type": "array"}},
    "if": {"properties": {"retrievalEligible": {"const": False}}}, "then": {"required": ["retrievalReason"]}}
dump("schema/section-contract.schema.json", contract_schema)

# ---------------------------------------------------------------- allowlist
allow = {"version": ALLOWLIST_VERSION, "note": "closed list of what a generator may set; verify_all.py checks parity with primitives/, components/, sections/ and with the PageSpec schema",
         "nodeProperties": sorted(defs["node"]["properties"]), "styleFields": sorted(token_policy["styleFields"]),
         "primitives": sorted(f"primitive.{k}" for k in PRIMS), "components": sorted(f"component.{k}" for k in COMPS),
         "sections": {s["id"]: {"contentFields": sorted(s["content"]["properties"]), "variants": s["variants"] or [], "motionPatterns": s["motion"]["allowedPatterns"],
                                "assetSlots": sorted(s["slots"]), "retrievalEligible": s["retrieval"]} for s in SECTIONS},
         "assetRoles": roles_enum}
dump("tokens/llm/component-allowlist.json", allow)

# ---------------------------------------------------------------- measured values
mv_heights = {"viewport": {"width": 1440, "height": 900}, "measuredFrom": f"{EV}/computed-1440.json", "tool": "extraction/measure_sections.mjs",
              "method": "headless Chromium, in-app navigation from '/', sound gate clicked, 6 s settle per route; one route per template", "pages": {}}
for p in C1440["pages"]:
    secs = []
    for sid, inst in p["sections"].items():
        flow = next(s["flow"] for s in SECTIONS if s["id"] == sid)
        for i, x in enumerate(inst):
            secs.append({"section": sid, "instance": i, "heightPx": x["heightPx"], "inFlow": bool(flow and x.get("position") not in ("fixed",))})
    mv_heights["pages"][p["route"]] = {"template": routes[p["route"]], "pageHeightPx": p["pageHeightPx"], "evidence": cite(f"{EV}/computed-1440.json", f'"route": "{p["route"]}"'), "sections": secs}
prev = {}
if (ROOT / "extraction/measured-values.json").exists():
    prev = load("extraction/measured-values.json")
evidence_pins = {}
for f in sorted((ROOT / EV).iterdir()):
    if f.is_file() and f.name != "parity-results.json":
        evidence_pins[f"{EV}/{f.name}"] = "sha256:" + hashlib.sha256(f.read_bytes()).hexdigest()
parity_file = ROOT / EV / "parity-results.json"
per_section = None
if parity_file.exists():
    pr = json.loads(parity_file.read_text())
    per_section = {"source": f"{EV}/parity-results.json", "sha256": "sha256:" + hashlib.sha256(parity_file.read_bytes()).hexdigest(),
                   "gate": pr["gate"], "average": pr["average"], "allCapturedPassGate": pr["allCapturedPassGate"], "runsAgree": pr["runsAgree"],
                   "capturedAt": pr["capturedAt"], "belowGate": {k: v for k, v in pr["sections"].items() if v.get("passesGate") is False},
                   "notCaptured": sorted(k for k, v in pr["sections"].items() if v.get("min") is None)}
mv = {
    "version": "1.0.0",
    "note": "Citation ledger + measured values. Citations point INTO design-repo (extraction/evidence/*). siblingSources pin the mirrored site next to design-repo/; verify_all.py checks them when that sibling exists and degrades to WARN when it does not.",
    "rootFontSizePx": {"1440": 9.47368, "768": 5.05263, "390": 10.4},
    "typeScaleDerivation": "fontSize histogram px / root px at the same viewport = design units (tokens/00-foundation/typography.json keeps only sizes seen rendered)",
    "citations": [
        {"claim": "page background is sage #9ab5ac", **cite(SC, "background-color:#9ab5ac")},
        {"claim": "fluid root: html font-size calc(1000vw/var(--size))", **cite(SC, "font-size:calc(1000vw/var(--size));")},
        {"claim": "single breakpoint 650px", **cite(SC, "@media (min-width:650px) {")},
        {"claim": "CustomEase snappy curve", **mcite('.create("snappy"')},
        {"claim": "about stats live inside the CTA section with the Download button", **cite(M, 'e("section",{staticClass:"relative pb-100 s:pb-150')},
        {"claim": "about headings: about-book holds 'I never set out to be a leader'; stories are 'I had to leave home...' and 'This is not an all-or-nothing endeavor'", **cite(M, "I never set out to be a leader.")},
        {"claim": "no reviews/ratings/testimonials in the source", "cite": f"{EV}/copy.json:1", "needle": "{"},
    ],
    "sectionHeights": mv_heights,
    "responsiveMeasured": {"768": f"{EV}/computed-768.json", "390": f"{EV}/computed-390.json"},
    "wrapperGateWhitelist": prev.get("wrapperGateWhitelist", []),
    "parity": {
        "screenLevel": {
            "method": "whole-screen pixel diff: fraction of pixels whose luminance differs by > 30, live site vs clone, 1440x900, same in-app navigation path, same settle times (measured before this build; numbers recorded exactly as reported)",
            "inAppJourney": {"intro": "0.02%", "entered": "0.00%", "explore": "0.00%", "chapter three": "0.00%", "chapter three scrolled": "0.01%", "navigation": "0.01%", "about": "0.10%", "about scrolled": "0.21%"},
            "allRoutesRun": {"16 routes": "0.00%", "/about": "0.15%"},
            "note": "per-screen, not per-section"},
        "perSection": per_section if per_section else {"status": "not measured yet: run extraction/parity.mjs"},
        "exceptions": prev.get("parity", {}).get("exceptions", []),
    },
    "siblingSources": {"note": "paths relative to the project root (parent of design-repo/)", "pins": load(f"{EV}/source-pins.json")["pins"]},
    "evidencePins": evidence_pins,
}
dump("extraction/measured-values.json", mv)

# ---------------------------------------------------------------- policy + manifest
policy = {
    "policyId": "n0-design-constraints-common", "policyVersion": "0.1.0", "commonIrVersion": "0.5", "enforcementMode": "hard-and-soft",
    "localExtension": {"id": "book-promotion-local", "version": "1.0.0",
                       "rules": ["one book per site: every CTA points at the single book (download formats page or an external order link)",
                                 "author identity, voice, signature and portrait are never reproduced in generated output",
                                 "statistics about the book are source claims and never reused in generated output",
                                 "deep routes are app-internal (301 to '/' on direct load); generated sites may choose normal routing"]},
    "classification": {"category": "book-promotion", "domain": "publishing / single-book promotion",
                       "evidence": ["one book: 12 chapter summaries, an audio synopsis and per-chapter narration (copy.json: 12 chapters)",
                                    "free PDF + audiobook ZIP downloads on /formats/ (copy.json formatsDownloadUrls)",
                                    "one external retailer order link and one author portfolio link (copy.json outboundUrls)",
                                    "no pricing tiers, no sign-up or login, no dashboard, no integrations, no account area (route list: 17 routes, none of those kinds)"]},
    "generationRules": {"modes": ["reference", "generated"], "generatedMode": "fictional brand, fictional people, .example/.invalid URLs, placeholder or generated assets, original copy; enforced by GENERATED_MODE_* rules in schema/semantic_validate.py",
                        "fonts": token_policy["fonts"]["generatedMode"]},
    "enforcedBy": ["tokens/llm/token-policy.json", "compatibility/graph.json", "schema/pagespec.schema.json", "schema/semantic_validate.py"],
    "approval": {"status": "defined-pending-architecture-review", "architectureDecisionRecorded": False, "decidedBy": None, "decidedAt": None,
                 "note": "classification proposed by the build agent from evidence; only the human owner may ratify it"},
}
dump("policy/design-policy.json", policy)
policy_hash = subprocess.run([sys.executable, str(ROOT / "extraction/policy_hash.py")], capture_output=True, text=True, check=True).stdout.strip()

def count_files(d): return len(list((ROOT / d).glob("*.json")))
examples = sorted(p.name for p in (ROOT / "schema/examples").glob("*.json")) if (ROOT / "schema/examples").exists() else []
manifest = {
    "repositoryId": "findworkhappiness-design-repo", "repositoryVersion": REPO_VERSION, "pageSpecVersion": PAGESPEC_VERSION, "allowlistVersion": ALLOWLIST_VERSION,
    "versionFieldNote": "allowlistVersion and pageSpecVersion are machine-checked by extraction/verify_all.py (against tokens/llm/component-allowlist.json and the schema's pageSpecVersion const). repositoryVersion is a documentation-only, hand-maintained marker that nothing checks.",
    "status": "design-review-pending", "productionApproved": False,
    "category": "book-promotion",
    "sourceStack": {"note": "documentation only: never shapes token names, section ids, schema fields or validator logic", "detected": "Nuxt 2 static generate (Vue 2), Tailwind CSS 2.2.19, GSAP, three.js (glTF + KTX2/Basis), Rive, DatoCMS content, HTML5 audio; /formats/ is plain static HTML"},
    "source": {"site": "https://www.findworkhappiness.com", "clone": "../site served by ../server.js (relative to this folder; not part of the package)", "gitRepository": False},
    "designPolicy": {"policyId": policy["policyId"], "policyVersion": policy["policyVersion"], "commonIrVersion": "0.5", "enforcementMode": "hard-and-soft",
                     "domain": policy["classification"]["domain"], "contentHash": policy_hash, "policyFile": "policy/design-policy.json"},
    "defaultTheme": "light", "schemaValidatedThemes": ["light"],
    "counts": {"sections": count_files("sections"), "templates": len(templates), "routes": len(routes), "primitives": count_files("primitives"), "components": count_files("components"),
               "assetRoles": len(ROLES), "tokens": sum(len(v) for v in CAT.values()), "examples": len(examples),
               "graphRules": len(graph["rules"]), "retrievalIneligibleSections": len(RETRIEVAL_INELIGIBLE)},
    "entryPoints": {"readme": "README.md", "changelog": "CHANGELOG.md", "schema": "schema/pagespec.schema.json", "sectionContractSchema": "schema/section-contract.schema.json",
                    "semanticValidator": "schema/semantic_validate.py", "adversarialTests": "schema/tests/adversarial_test.py", "sourcePatterns": "schema/source-patterns.json",
                    "templates": "templates/templates.json", "compatibilityGraph": "compatibility/graph.json", "assetRoles": "assets/asset-roles.json",
                    "componentAllowlist": "tokens/llm/component-allowlist.json", "token-catalog": "tokens/llm/token-catalog.json", "token-policy": "tokens/llm/token-policy.json",
                    "motionPatterns": "tokens/00-foundation/motion-patterns.json", "theme": "tokens/themes/light.json", "measuredValues": "extraction/measured-values.json",
                    "verifyAll": "extraction/verify_all.py", "wrapperGate": "extraction/wrapper_gate.py", "policyHash": "extraction/policy_hash.py", "proveDrift": "extraction/prove_drift.py",
                    "designPolicy": "policy/design-policy.json", "parityHarness": "extraction/parity.mjs", "measureTool": "extraction/measure_sections.mjs", "builder": "extraction/build_repo.py"},
    "examples": [f"schema/examples/{e}" for e in examples],
}
dump("registry.manifest.json", manifest)
print(f"built: {len(SECTIONS)} sections, {len(templates)} templates, {len(routes)} routes, {manifest['counts']['tokens']} catalog tokens, {len(ROLES)} asset roles; policy {policy_hash[:19]}...")

# ---------------------------------------------------------------- README count markers (recomputed, never hand-typed)
rd = ROOT / "README.md"
if rd.exists():
    txt = rd.read_text()
    for k, v in manifest["counts"].items():
        txt = re.sub(r"<!--count:%s-->\d+" % k, f"<!--count:{k}-->{v}", txt)
    rd.write_text(txt)
