#!/usr/bin/env python3
"""Adversarial suite: every rule must reject a mutated PageSpec / registry, every control must pass.

    python3 schema/tests/adversarial_test.py         # exit 1 if any mutation is accepted or any control fails

Mutation classes (BUILD-GUIDE 2.8 + BASELINE R5, R8, R9, R10):
  schema layer, structure/template, routes, graph rules, word budgets, motion, asset slots/roles,
  generated-mode leakage (brand, logo, store, statistic, person, likeness, URL, copy, CTA, media, font licence),
  retrieval pins (node / contract / allowlist), availability pins, wrapper gate, token policy, graph drift.
Controls: every bundled example; one synthesized generated AND one synthesized reference PageSpec per
template, built generically from templates.json + the content contracts (a new template is covered
automatically); a whitelisted tall hero; a licensed-font generated page.
Registry-level mutations run against a scratch copy in a fresh temp dir; the real repo is never edited.
"""
import copy, importlib.util, json, re, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def mod(rel, name):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

sv = mod("schema/semantic_validate.py", "semantic_validate")
wg = mod("extraction/wrapper_gate.py", "wrapper_gate")
EX = {p.stem.replace(".pagespec", ""): json.loads(p.read_text()) for p in sorted((ROOT / "schema/examples").glob("*.json"))}
REF, GI, GC, GA, GF = (EX[k] for k in ("reference.chapter-one", "generated.intro", "generated.chapter", "generated.about", "generated.download-formats"))
TEMPLATES = json.loads((ROOT / "templates/templates.json").read_text())["templates"]
SCHEMA = json.loads((ROOT / "schema/pagespec.schema.json").read_text())
CONTRACTS = {p.stem: json.loads(p.read_text()) for p in (ROOT / "sections").glob("*.json")}

passed, failed = [], []
def result(name, ok, detail=""):
    (passed if ok else failed).append(f"{name}{(': ' + detail) if detail else ''}")

def run(spec, root=None):
    r = sv.validate(spec, root)
    return {x["rule"] for x in r if x["severity"] == "error"}, {x["rule"] for x in r if x["severity"] == "warn"}

def idx(spec, section, variant=None):
    return next(i for i, n in enumerate(spec["nodes"]) if n["section"] == section and (variant is None or n.get("variant") == variant))

def node(spec, section, variant=None):
    return spec["nodes"][idx(spec, section, variant)]

def mutate(name, base, fn, expect, severity="error"):
    s = copy.deepcopy(base)
    fn(s)
    errs, warns = run(s)
    got = errs if severity == "error" else warns
    result(f"MUTATION {name}", expect in got, f"expected {expect}, got errors={sorted(errs)} warns={sorted(warns)}" if expect not in got else "")

def control(name, spec, root=None):
    errs, _ = run(spec, root)
    result(f"CONTROL  {name}", not errs, f"unexpected errors {sorted(errs)}" if errs else "")

# ----------------------------------------------------------------- controls
for k, s in EX.items():
    control(f"example {k}", s)

POOL = ["amber", "orchard", "lantern", "harbor", "willow", "meadow", "pebble", "cobalt", "juniper", "saffron"]
def synth(schema, key=""):
    if "$ref" in schema:
        schema = SCHEMA["definitions"][schema["$ref"].split("/")[-1]]
    t = schema.get("type")
    if "enum" in schema: return schema["enum"][0]
    if t == "object":
        return {k: synth(v, k) for k, v in schema.get("properties", {}).items() if k in schema.get("required", [])}
    if t == "array":
        return [synth(schema["items"], key) for _ in range(schema.get("minItems", 0))]
    if t == "boolean": return False
    if t == "integer": return schema.get("minimum", 1)
    pat = schema.get("pattern", "")
    if pat.startswith("^/"): return "/sample"
    if ":[0-5]" in pat: return "1:00"
    if pat == "^[0-9]{2}$": return "07"
    if pat.startswith("^[0-9]"): return "42"
    if "href" in key.lower(): return "https://sample.example/"
    n = min(schema.get("maxWords", 3), 3)
    return " ".join(POOL[:n])

def synth_page(tid, mode):
    t = TEMPLATES[tid]
    route = t["routes"][0] if mode == "reference" else next(r for r in ("/", "/sample", "/chapter/sample", "/sample/") if re.match(t["routePattern"], r))
    nodes = []
    for tn in t["nodes"]:
        c = CONTRACTS[tn["section"]]
        n = {"section": tn["section"], "content": synth({"$ref": f"#/definitions/content.{tn['section']}"}), "motion": dict(c["motion"]["default"])}
        if tn.get("variant"): n["variant"] = tn["variant"]
        assets = []
        for slot, sd in c["assetSlots"].items():
            role = (sd["generatedRoles"] if mode == "generated" else sd["referenceRoles"] or sd["generatedRoles"])[0]
            assets += [{"slot": slot, "role": role, "src": f"https://sample.example/{slot}-{i}.webp", "alt": "sample asset"} for i in range(sd["minItems"])]
        if assets: n["assets"] = assets
        nodes.append(n)
    s = {"pageSpecVersion": SCHEMA["properties"]["pageSpecVersion"]["const"], "mode": mode, "template": tid, "route": route, "theme": "light",
         "meta": {"title": "Sample page", "description": "Synthesized control page."}, "nodes": nodes}
    if mode == "generated": s["fontLicence"] = "fallback"
    return s

for tid in TEMPLATES:
    control(f"synthesized generated '{tid}'", synth_page(tid, "generated"))
    control(f"synthesized reference '{tid}'", synth_page(tid, "reference"))
lic = copy.deepcopy(GC); lic["fontLicence"] = "licensed-by-deployer"; node(lic, "chapter.header")["style"]["fontFamily"] = "font.display"
control("generated page with licensed Founders Grotesk", lic)

# ----------------------------------------------------------------- schema layer
def setp(path_fn): return path_fn
mutate("wrong enum (theme dark)", REF, lambda s: s.update(theme="dark"), "SCHEMA")
mutate("missing required meta", REF, lambda s: s.pop("meta"), "SCHEMA")
mutate("missing mode", REF, lambda s: s.pop("mode"), "SCHEMA")
mutate("mode outside enum", REF, lambda s: s.update(mode="draft"), "SCHEMA")
mutate("pageSpecVersion drift", REF, lambda s: s.update(pageSpecVersion="0.9.0"), "SCHEMA")
mutate("invented section alias", REF, lambda s: s["nodes"].insert(3, {"section": "hero.marketing", "content": {}, "motion": {"pattern": "fade", "trigger": "load", "reducedMotionFallback": "instant-opacity"}}), "SCHEMA")
mutate("missing reducedMotionFallback", REF, lambda s: node(s, "chapter.body")["motion"].pop("reducedMotionFallback"), "SCHEMA")
mutate("missing reducedMotionFallback (semantic)", REF, lambda s: node(s, "chapter.body")["motion"].pop("reducedMotionFallback"), "MOTION_FALLBACK_MISSING")
mutate("invented motion field", REF, lambda s: node(s, "chapter.body")["motion"].update(inventedAnimation="wobble"), "SCHEMA")
mutate("extra content property", REF, lambda s: node(s, "chapter.header")["content"].update(subtitle="extra"), "SCHEMA")
mutate("invented asset role", REF, lambda s: node(s, "chapter.header")["assets"][0].update(role="brand.logo"), "SCHEMA")
mutate("variant missing on repeatable section", GA, lambda s: node(s, "gallery.illustration-strip", "a").pop("variant"), "SCHEMA")
mutate("variant on a non-variant section", REF, lambda s: node(s, "chapter.body").update(variant="a"), "SCHEMA")
mutate("generated page without fontLicence", GC, lambda s: s.pop("fontLicence"), "SCHEMA")
mutate("unknown top-level field", REF, lambda s: s.update(tracking="ga"), "SCHEMA")

# ----------------------------------------------------------------- structure / template / routes
mutate("duplicate one-per-page section", REF, lambda s: s["nodes"].insert(4, copy.deepcopy(node(s, "chapter.header"))), "ONE_PER_PAGE")
mutate("removed mandatory section", REF, lambda s: s["nodes"].pop(idx(s, "chapter.body")), "TEMPLATE_REQUIRED_MISSING")
def swap(a, b):
    def f(s):
        i, j = idx(s, *a), idx(s, *b); s["nodes"][i], s["nodes"][j] = s["nodes"][j], s["nodes"][i]
    return f
mutate("reordered sections", REF, swap(("chapter.header",), ("chapter.body",)), "TEMPLATE_SEQUENCE")
mutate("body before header", REF, swap(("chapter.header",), ("chapter.body",)), "CHAPTER_HEADER_BEFORE_BODY")
mutate("template/node mismatch", REF, lambda s: s.update(template="about"), "TEMPLATE_EXTRA_SECTION")
mutate("section from another template", REF, lambda s: s["nodes"].insert(6, copy.deepcopy(node(GA, "shell.footer"))), "TEMPLATE_EXTRA_SECTION")
mutate("unknown template", REF, lambda s: s.update(template="pricing"), "TEMPLATE_UNKNOWN")
mutate("reference route not in template", REF, lambda s: s.update(route="/chapter/thirteen"), "ROUTE_NOT_IN_TEMPLATE")
mutate("generated route breaks pattern", GC, lambda s: s.update(route="/stories/first-light"), "ROUTE_PATTERN")
mutate("home-only section off home", GI, lambda s: s.update(route="/home"), "HOME_ROUTE_ONLY")
mutate("second hero", GA, lambda s: s["nodes"].insert(4, copy.deepcopy(node(GI, "hero.book-intro"))), "ONE_HERO")
mutate("hero not first in flow", GA, swap(("hero.about-title",), ("content.about-book",)), "HERO_FIRST_IN_FLOW")
mutate("footer not last", GA, swap(("cta.download-closer",), ("shell.footer",)), "FOOTER_LAST")
mutate("closer not before footer", GA, swap(("cta.download-closer",), ("shell.footer",)), "CTA_BEFORE_FOOTER")
mutate("same (section,variant) twice in a row", GA, lambda s: s["nodes"].insert(idx(s, "gallery.illustration-strip", "a"), copy.deepcopy(node(s, "gallery.illustration-strip", "a"))), "NO_CONSECUTIVE_SAME_VARIANT")
mutate("adjacent same category (warn)", GA, swap(("gallery.illustration-strip", "b"), ("content.about-story", "a")), "NO_ADJACENT_SAME_CATEGORY", "warn")
def three_loops(s):
    node(s, "runtime.preloader")["motion"].update(pattern="pulse-loop")
    node(s, "hero.book-intro")["motion"].update(pattern="spin-loop")
    node(s, "media.audio-player")["motion"].update(pattern="pulse-loop")
mutate("looping motion over budget (warn)", GI, three_loops, "MOTION_BUDGET", "warn")

# ----------------------------------------------------------------- word budgets
mutate("maxWords overflow (headline)", REF, lambda s: node(s, "chapter.header")["content"].update(headline=" ".join(["word"] * 13)), "MAX_WORDS")
mutate("maxWordsTotal overflow (body)", REF, lambda s: node(s, "chapter.body")["content"].update(paragraphs=[{"text": " ".join(["word"] * 50)} for _ in range(4)]), "MAX_WORDS_TOTAL")
mutate("maxWords overflow (meta description)", REF, lambda s: s["meta"].update(description=" ".join(["word"] * 31)), "MAX_WORDS")
mutate("maxWords overflow (about story heading)", GA, lambda s: node(s, "content.about-story", "a")["content"].update(heading=" ".join(["word"] * 11)), "MAX_WORDS")

# ----------------------------------------------------------------- motion
mutate("motion pattern not allowed", REF, lambda s: node(s, "chapter.body")["motion"].update(pattern="spin-loop"), "MOTION_PATTERN_NOT_ALLOWED")
mutate("fallback not valid for pattern", REF, lambda s: node(s, "chapter.header")["motion"].update(reducedMotionFallback="instant-opacity"), "MOTION_FALLBACK_MISMATCH")
mutate("trigger not valid for pattern", REF, lambda s: node(s, "shell.header-nav")["motion"].update(trigger="drag"), "MOTION_TRIGGER_MISMATCH")
mutate("unknown duration token", REF, lambda s: node(s, "chapter.body")["motion"].update(durationToken="duration.420ms"), "TOKEN_UNKNOWN")

# ----------------------------------------------------------------- assets
mutate("unknown asset slot", REF, lambda s: node(s, "chapter.header")["assets"][0].update(slot="hero"), "ASSET_SLOT_UNKNOWN")
mutate("role not allowed in slot", REF, lambda s: node(s, "chapter.header")["assets"][0].update(role="book.cover"), "ASSET_ROLE_NOT_ALLOWED")
mutate("required slot empty", GI, lambda s: node(s, "hero.book-intro")["assets"].pop(2), "ASSET_SLOT_COUNT")

# ----------------------------------------------------------------- R5 generated-mode leakage
mutate("brand name leakage", GI, lambda s: node(s, "hero.book-intro")["content"].update(tagline="The Search for Work Happiness, retold"), "GENERATED_MODE_BRAND")
mutate("brand domain variant leakage", GI, lambda s: s["meta"].update(title="findworkhappiness field notes"), "GENERATED_MODE_BRAND")
mutate("logo / wordmark reuse", GI, lambda s: node(s, "hero.book-intro")["assets"][2].update(role="brand.wordmark", src="/text-logo.svg"), "GENERATED_MODE_ASSET")
mutate("store link leakage", GA, lambda s: node(s, "shell.footer")["content"].update(linkHref="https://www.amazon.com/dp/B0BWSL3CRG"), "GENERATED_MODE_STORE")
mutate("store mark text leakage", GA, lambda s: node(s, "shell.footer")["content"].update(linkLabel="Buy on amazon.com"), "GENERATED_MODE_STORE")
mutate("source statistic leakage (rating-class claim)", GA, lambda s: node(s, "cta.download-closer")["content"]["stats"][1].update(value="1,039", label="copies sold"), "GENERATED_MODE_STATISTIC")
mutate("person identity leakage", GA, lambda s: node(s, "shell.footer")["content"].update(copyright="© 2023 David Lubofsky"), "GENERATED_MODE_PERSON")
mutate("person handle leakage", GA, lambda s: node(s, "shell.footer")["assets"][0].update(alt="davidlubofsky portfolio"), "GENERATED_MODE_PERSON")
mutate("real person likeness (portrait)", GI, lambda s: node(s, "hero.book-intro")["assets"][0].update(role="author.portrait", src="/dl.png"), "GENERATED_MODE_ASSET")
mutate("real signature reuse", GA, lambda s: node(s, "cta.download-closer")["assets"][1].update(role="author.signature"), "GENERATED_MODE_ASSET")
mutate("source URL leakage", GA, lambda s: node(s, "shell.footer")["content"].update(linkHref="https://www.davidlubofsky.com"), "GENERATED_MODE_URL")
mutate("download endpoint leakage", GF, lambda s: node(s, "cta.download-formats", "print")["content"].update(href="https://book.findworkhappiness.com/The-Search-for-Work-Happiness-Book.pdf"), "GENERATED_MODE_URL")
mutate("non-reserved host", GF, lambda s: node(s, "cta.download-formats", "print")["content"].update(href="https://lanternledger.com/guide.pdf"), "GENERATED_MODE_URL")
mutate("source copy leakage (headline)", GC, lambda s: node(s, "chapter.header")["content"].update(headline="Support their dreams—or they’ll dream of leaving"), "GENERATED_MODE_COPY")
mutate("source copy leakage (6-word run)", GC, lambda s: node(s, "chapter.body")["content"]["paragraphs"][1].update(text="Honestly, it was the most eye-opening experience of my life so far."), "GENERATED_MODE_COPY")
mutate("source tagline leakage", GI, lambda s: node(s, "hero.book-intro")["content"].update(tagline="Anecdotes to help leaders keep themselves and their people happy and mentally healthy."), "GENERATED_MODE_COPY")
mutate("source CTA leakage", GI, lambda s: node(s, "runtime.sound-gate")["content"].update(label="Enter without sound"), "GENERATED_MODE_CTA")
mutate("source CTA leakage (nav)", GC, lambda s: node(s, "shell.header-nav")["content"]["primaryLinks"][0].update(label="Chapter summaries"), "GENERATED_MODE_CTA")
mutate("proprietary media path", GA, lambda s: node(s, "cta.download-closer")["assets"][0].update(src="/cover.jpg"), "GENERATED_MODE_ASSET")
mutate("proprietary CMS media path", GC, lambda s: node(s, "chapter.header")["assets"][0].update(src="/dato/96103/1683049429-01_chapter-content.svg"), "GENERATED_MODE_ASSET")
mutate("narrator voice reuse", GC, lambda s: node(s, "media.audio-player")["assets"][0].update(role="audio.narration"), "GENERATED_MODE_ASSET")
mutate("unlicensed commercial font", GC, lambda s: node(s, "chapter.header")["style"].update(fontFamily="font.display"), "GENERATED_MODE_FONT_LICENCE")
result("DOCUMENTED GENERATED_MODE_RATING not applicable", "GENERATED_MODE_RATING" in sv.NOT_APPLICABLE_RULES and json.loads((ROOT / "schema/source-patterns.json").read_text())["rating"]["patterns"] == [] and "rating" not in json.dumps(SCHEMA["definitions"]["node"]))

# ----------------------------------------------------------------- R8 retrieval (node level)
mutate("runtime node flipped eligible", REF, lambda s: node(s, "runtime.cursor").update(retrievalEligible=True), "RUNTIME_NOT_RETRIEVABLE")
mutate("content node marked ineligible", REF, lambda s: node(s, "chapter.body").update(retrievalEligible=False), "RUNTIME_NOT_RETRIEVABLE")

# ----------------------------------------------------------------- R10 token policy
mutate("unknown token", REF, lambda s: node(s, "chapter.body")["style"].update(surface="surface.brand"), "TOKEN_UNKNOWN")
mutate("raw hex colour", REF, lambda s: node(s, "chapter.body")["style"].update(surface="#ffeb35"), "TOKEN_RAW_COLOR")
mutate("raw rgb colour", REF, lambda s: node(s, "chapter.body")["style"].update(text="rgb(34, 35, 36)"), "TOKEN_RAW_COLOR")
mutate("named colour", REF, lambda s: node(s, "chapter.body")["style"].update(surface="yellow"), "TOKEN_RAW_COLOR")
mutate("arbitrary spacing", REF, lambda s: node(s, "chapter.body")["style"].update(paddingBlock="24px"), "TOKEN_ARBITRARY_SPACING")
mutate("arbitrary unitless spacing", REF, lambda s: node(s, "chapter.body")["style"].update(gap="13"), "TOKEN_ARBITRARY_SPACING")
mutate("unsupported font", REF, lambda s: node(s, "chapter.body")["style"].update(fontFamily="Inter"), "TOKEN_UNSUPPORTED_FONT")
mutate("invalid theme combination", REF, lambda s: node(s, "chapter.body")["style"].update(surface="surface.inverse", text="text.primary"), "TOKEN_INVALID_COMBINATION")
mutate("token from wrong category", REF, lambda s: node(s, "chapter.body")["style"].update(surface="space.15"), "TOKEN_WRONG_CATEGORY")
mutate("spacing slot given a type token", REF, lambda s: node(s, "chapter.body")["style"].update(paddingBlock="fontSize.20"), "TOKEN_WRONG_CATEGORY")
mutate("unsupported theme", REF, lambda s: s.update(theme="dark"), "SCHEMA")

# ----------------------------------------------------------------- registry-level mutations (scratch copies)
def scratch(edit):
    d = Path(tempfile.mkdtemp(prefix="adv-")) / "design-repo"
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns("__pycache__"))
    edit(d)
    return d
def jedit(rel, fn):
    def e(d):
        p = d / rel; o = json.loads(p.read_text()); fn(o); p.write_text(json.dumps(o, indent=2))
    return e
def reg_case(name, edit, expect, spec=REF):
    d = scratch(edit)
    try:
        errs, _ = run(spec, d)
        result(f"MUTATION {name}", expect in errs, f"expected {expect}, got {sorted(errs)}" if expect not in errs else "")
    finally:
        shutil.rmtree(d.parent, ignore_errors=True)
reg_case("contract flips runtime section eligible", jedit("sections/runtime.preloader.json", lambda o: o.update(retrievalEligible=True)), "CONTRACT_RETRIEVAL_DRIFT")
reg_case("allowlist flips runtime section eligible", jedit("tokens/llm/component-allowlist.json", lambda o: o["sections"]["runtime.cursor"].update(retrievalEligible=True)), "ALLOWLIST_RETRIEVAL_DRIFT")
def both(d):
    jedit("sections/runtime.sound-gate.json", lambda o: o.update(retrievalEligible=True))(d)
    jedit("tokens/llm/component-allowlist.json", lambda o: o["sections"]["runtime.sound-gate"].update(retrievalEligible=True))(d)
reg_case("contract + allowlist flipped together", both, "CONTRACT_RETRIEVAL_DRIFT")
reg_case("content contract marked ineligible", jedit("sections/chapter.body.json", lambda o: o.update(retrievalEligible=False)), "CONTRACT_RETRIEVAL_DRIFT")
reg_case("registry loosens real likeness to generation-safe", jedit("assets/asset-roles.json", lambda o: o["roles"]["author.portrait"].update(availability="generation-safe")), "REGISTRY_PIN_DRIFT")
loosened = copy.deepcopy(GI); node(loosened, "hero.book-intro")["assets"][0]["role"] = "author.portrait"
def loosen_all(d):
    jedit("assets/asset-roles.json", lambda o: o["roles"]["author.portrait"].update(availability="generation-safe"))(d)
    jedit("sections/hero.book-intro.json", lambda o: o["assetSlots"]["portrait"]["generatedRoles"].append("author.portrait"))(d)
reg_case("registry + contract loosened: pin still blocks likeness", loosen_all, "GENERATED_MODE_ASSET", loosened)
reg_case("graph severity edited without validator", jedit("compatibility/graph.json", lambda o: o["rules"]["FOOTER_LAST"].update(severity="warn")), "GRAPH_VALIDATOR_DRIFT")
muted = copy.deepcopy(REF); node(muted, "chapter.body")["style"] = {"surface": "surface.muted"}
reg_case("token not resolved by theme", jedit("tokens/themes/light.json", lambda o: o["resolved"].pop("surface.muted")), "TOKEN_NOT_IN_THEME", muted)

# ----------------------------------------------------------------- R9 wrapper gate
MV = json.loads((ROOT / "extraction/measured-values.json").read_text())
def gate_case(name, fn, expect, kind="error", wl=None):
    m = copy.deepcopy(MV); fn(m)
    if wl is not None: m["wrapperGateWhitelist"] = wl
    e, w = wg.run(ROOT, measured=m)
    pool = e if kind == "error" else w
    ok = any(x.startswith(expect) for x in pool) and (kind == "error" or not e)
    result(f"{'MUTATION' if kind == 'error' else 'CONTROL '} wrapper gate: {name}", ok, f"expected {kind} {expect}; errors={e[:2]} warnings={w[:2]}" if not ok else "")
def hero(px):
    def f(m):
        s = next(x for x in m["sectionHeights"]["pages"]["/about"]["sections"] if x["section"] == "hero.about-title"); s["heightPx"] = px
    return f
gate_case("HERO 1900px warns", hero(1900), "WRAPPER_HERO_TALL", "warn")
gate_case("HERO 3100px fails", hero(3100), "WRAPPER_HERO_TOO_TALL")
def majority(m):
    p = m["sectionHeights"]["pages"]["/about"]; next(x for x in p["sections"] if x["section"] == "content.about-book")["heightPx"] = 9000; p["pageHeightPx"] = 13000
gate_case("one section holds > 60% of the page", majority, "WRAPPER_MAJORITY_SHARE")
gate_case("whitelist entry without justification", hero(3100), "WRAPPER_WHITELIST_INVALID", wl=[{"section": "hero.about-title", "route": "/about", "reviewedBy": "owner", "justification": "", "maxHeightPx": 3200}])
gate_case("agent reviewer without attestation", hero(3100), "WRAPPER_WHITELIST_INVALID", wl=[{"section": "hero.about-title", "route": "/about", "reviewedBy": "build agent", "justification": "a genuinely tall illustrated opener reviewed by hand", "maxHeightPx": 3200}])
gate_case("whitelisted 3100px hero still warns", hero(3100), "WRAPPER_HERO_TALL", "warn", wl=[{"section": "hero.about-title", "route": "/about", "reviewedBy": "site owner", "justification": "a genuinely tall illustrated opener reviewed by hand", "maxHeightPx": 3200}])
gate_case("whitelist cap below measured height", hero(3300), "WRAPPER_WHITELIST_OVER_CAP", wl=[{"section": "hero.about-title", "route": "/about", "reviewedBy": "site owner", "justification": "a genuinely tall illustrated opener reviewed by hand", "maxHeightPx": 3200}])
gate_case("stale whitelist entry", lambda m: None, "WRAPPER_WHITELIST_STALE", wl=[{"section": "hero.about-title", "route": "/about", "reviewedBy": "site owner", "justification": "a genuinely tall illustrated opener reviewed by hand", "maxHeightPx": 3200}])
def missing(m):
    p = m["sectionHeights"]["pages"]["/chapter/one"]; p["sections"] = [x for x in p["sections"] if x["section"] != "chapter.body"]
gate_case("missing measurement", missing, "WRAPPER_MISSING_MEASUREMENT")
gate_case("measured at wrong viewport", lambda m: m["sectionHeights"]["viewport"].update(width=1280), "WRAPPER_WRONG_VIEWPORT")
gate_case("no sectionHeights at all", lambda m: m.pop("sectionHeights"), "WRAPPER_MISSING_MEASUREMENT")

# ----------------------------------------------------------------- report
for x in passed: print("ok   ", x)
for x in failed: print("FAIL ", x)
mut = [x for x in passed + failed if x.startswith("MUTATION")]
ctl = [x for x in passed + failed if x.startswith("CONTROL")]
print(f"\nadversarial: {sum(1 for x in passed if x.startswith('MUTATION'))}/{len(mut)} mutations rejected, "
      f"{sum(1 for x in passed if x.startswith('CONTROL'))}/{len(ctl)} controls pass, {len(failed)} failure(s)")
sys.exit(1 if failed else 0)
