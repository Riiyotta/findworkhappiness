#!/usr/bin/env python3
"""Semantic validator for PageSpecs: everything Draft-07 cannot express.

    python3 schema/semantic_validate.py <pagespec.json> [...]     # exit 1 on any error
    python3 schema/semantic_validate.py --examples                # every schema/examples/*.json

Library use: validate(spec, root=None) -> list of {"severity", "rule", "path", "message"}.
All registries are read relative to the repo root derived from __file__ (or the `root` argument,
which the adversarial suite uses to point at a mutated scratch copy). No absolute paths.

Rule families
  SCHEMA                          Draft-07 validation of schema/pagespec.schema.json
  TEMPLATE_*                      PageSpec node sequence cross-referenced against its declared template
  ROUTE_*, HOME_ROUTE_ONLY        route rules (reference: route must be one of the template's routes)
  graph rules                     ids/severities in compatibility/graph.json == GRAPH_RULES below
  MAX_WORDS, MAX_WORDS_TOTAL      per-field / per-array word budgets from the content contracts
  MOTION_*                        allowed patterns per section, closed fallback per pattern
  ASSET_*                         asset slots and roles per section contract
  GENERATED_MODE_*                source identity / content leakage when mode == generated
  TOKEN_*                         token policy for node.style (tokens/llm/token-policy.json)
  *_PIN_DRIFT / *_DRIFT           registry edits that contradict the pins in this file
"""
import json, re, sys
from pathlib import Path

try:
    from jsonschema import Draft7Validator
except ImportError:  # the schema layer is mandatory; fail loudly rather than skip it
    sys.exit("jsonschema is required (pip install jsonschema)")

ROOT = Path(__file__).resolve().parent.parent

# ---- pins (R3, R8): editing the registries alone cannot loosen these -------------------------
PINNED_AVAILABILITY = {
    "brand.wordmark": "reference-only", "brand.favicon": "reference-only", "book.cover": "reference-only",
    "book.3d-model": "blocked-for-generation", "illustration.chapter": "blocked-for-generation",
    "illustration.map-tiles": "blocked-for-generation", "illustration.about-scene": "blocked-for-generation",
    "author.portrait": "blocked-for-generation", "author.signature": "blocked-for-generation",
    "badge.text-image": "reference-only", "audio.narration": "blocked-for-generation", "audio.ambient-loop": "reference-only",
    "animation.rive": "reference-only", "cursor.custom": "reference-only", "texture.noise": "reference-only",
    "link.outbound": "blocked-for-generation", "link.download": "blocked-for-generation",
    "generated.brand-mark": "generation-safe", "generated.fictional-person": "generation-safe", "generated.signature": "generation-safe",
    "generated.product-visual": "generation-safe", "generated.illustration": "generation-safe", "generated.badge": "generation-safe",
    "placeholder.url": "generation-safe", "placeholder.audio": "generation-safe", "placeholder.rating": "generation-safe",
    "original.copy": "generation-safe",
}
RETRIEVAL_INELIGIBLE = {"runtime.preloader", "runtime.sound-gate", "runtime.cursor", "runtime.webgl-stage"}
RUNTIME_NAME_RE = re.compile(r"preload|loader|cursor|cookie|consent|modal|dialog|drawer|overlay|toast|sound-gate|webgl|spinner", re.I)

GRAPH_RULES = {  # must equal compatibility/graph.json rules (id -> severity)
    "ONE_HERO": "error", "HERO_FIRST_IN_FLOW": "error", "FOOTER_LAST": "error", "CTA_BEFORE_FOOTER": "error",
    "ONE_PER_PAGE": "error", "NO_CONSECUTIVE_SAME_VARIANT": "error", "NO_ADJACENT_SAME_CATEGORY": "warn",
    "CHAPTER_HEADER_BEFORE_BODY": "error", "HOME_ROUTE_ONLY": "error", "RUNTIME_NOT_RETRIEVABLE": "error", "MOTION_BUDGET": "warn",
}
GENERATED_MODE_RULES = ["GENERATED_MODE_BRAND", "GENERATED_MODE_PERSON", "GENERATED_MODE_URL", "GENERATED_MODE_STORE", "GENERATED_MODE_CTA",
                        "GENERATED_MODE_COPY", "GENERATED_MODE_STATISTIC", "GENERATED_MODE_ASSET", "GENERATED_MODE_FONT_LICENCE"]
NOT_APPLICABLE_RULES = {"GENERATED_MODE_RATING": "the source has no reviews, ratings or testimonials and the PageSpec has no rating field; nothing grounded to match (see schema/source-patterns.json rating.note)"}
LOOPING_PATTERNS = {"pulse-loop", "spin-loop"}
MOTION_BUDGET_MAX_LOOPING = 2
RESERVED_HOST_SUFFIXES = (".example", ".invalid")
CSS_NAMED_COLORS = {"black", "white", "red", "green", "blue", "yellow", "gray", "grey", "orange", "purple", "pink", "brown", "transparent", "currentcolor"}


class Repo:
    def __init__(self, root):
        r = Path(root)
        j = lambda rel: json.loads((r / rel).read_text())
        self.root = r
        self.schema = j("schema/pagespec.schema.json")
        self.templates = j("templates/templates.json")
        self.graph = j("compatibility/graph.json")
        self.roles = j("assets/asset-roles.json")["roles"]
        self.allow = j("tokens/llm/component-allowlist.json")
        self.catalog = j("tokens/llm/token-catalog.json")["categories"]
        self.policy = j("tokens/llm/token-policy.json")
        self.theme = j("tokens/themes/light.json")
        self.patterns = j("schema/source-patterns.json")
        self.motion = j("tokens/00-foundation/motion-patterns.json")["patterns"]
        self.contracts = {p.stem: json.loads(p.read_text()) for p in sorted((r / "sections").glob("*.json"))}
        self.validator = Draft7Validator(self.schema)
        self.all_tokens = {k for cat in self.catalog.values() for k in cat}
        self.corpus = self._corpus(r)

    @staticmethod
    def _corpus(r):
        texts = []
        c = json.loads((r / "extraction/evidence/computed-1440.json").read_text())
        for p in c["pages"]:
            for inst in p["sections"].values():
                for x in inst:
                    t = x.get("text")
                    texts.extend(t if isinstance(t, list) else [t or ""])
        copy = json.loads((r / "extraction/evidence/copy.json").read_text())
        texts += [copy["site"]["title"], copy["site"]["description"]] + [ch["introTitle"] for ch in copy["chapters"]]
        n = json.loads((r / "schema/source-patterns.json").read_text())["copy"]["shingleWords"]
        sh = set()
        for t in texts:
            w = words(norm(t))
            sh.update(tuple(w[i:i + n]) for i in range(len(w) - n + 1))
        return n, sh


def norm(s):
    s = str(s).lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()

def words(s):
    return re.findall(r"[a-z0-9']+", s)

def wc(s):
    return len(str(s).split())

def strings(obj, path="$"):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from strings(v, f"{path}[{i}]")


def validate(spec, root=None):
    repo = Repo(root or ROOT)
    out = []
    def err(rule, path, msg, sev="error"):
        out.append({"severity": sev, "rule": rule, "path": path, "message": msg})

    # 0. registry integrity against the pins in this file
    for role, av in PINNED_AVAILABILITY.items():
        got = repo.roles.get(role, {}).get("availability")
        if got != av:
            err("REGISTRY_PIN_DRIFT", f"assets/asset-roles.json:{role}", f"availability {got!r} != pinned {av!r}")
    for role in repo.roles:
        if role not in PINNED_AVAILABILITY:
            err("REGISTRY_PIN_DRIFT", f"assets/asset-roles.json:{role}", "role not pinned in code")
    for sid, c in repo.contracts.items():
        pinned = sid in RETRIEVAL_INELIGIBLE
        if c.get("retrievalEligible") is not (not pinned):
            err("CONTRACT_RETRIEVAL_DRIFT", f"sections/{sid}.json", f"retrievalEligible {c.get('retrievalEligible')} contradicts the code pin")
        if RUNTIME_NAME_RE.search(sid + " " + c.get("title", "")) and not pinned:
            err("CONTRACT_RETRIEVAL_DRIFT", f"sections/{sid}.json", "looks like runtime/utility UI but is not in RETRIEVAL_INELIGIBLE")
        a = repo.allow["sections"].get(sid, {})
        if a.get("retrievalEligible") is not (not pinned):
            err("ALLOWLIST_RETRIEVAL_DRIFT", f"tokens/llm/component-allowlist.json:{sid}", "retrievalEligible contradicts the code pin")
    graph_rules = {k: v["severity"] for k, v in repo.graph["rules"].items()}
    if graph_rules != GRAPH_RULES:
        err("GRAPH_VALIDATOR_DRIFT", "compatibility/graph.json", f"graph rules {sorted(graph_rules.items())} != validator {sorted(GRAPH_RULES.items())}")

    # 1. schema
    for e in sorted(repo.validator.iter_errors(spec), key=lambda e: list(e.absolute_path)):
        err("SCHEMA", "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in e.absolute_path), e.message[:300])
    if not isinstance(spec, dict) or not isinstance(spec.get("nodes"), list):
        return out
    nodes = [n for n in spec["nodes"] if isinstance(n, dict) and n.get("section") in repo.contracts]
    mode = spec.get("mode")
    tid = spec.get("template")
    tpl = repo.templates["templates"].get(tid)
    route = spec.get("route", "")

    # 2. template cross-reference
    if not tpl:
        err("TEMPLATE_UNKNOWN", "$.template", f"unknown template {tid!r}")
    else:
        T = tpl["nodes"]
        match = lambda t, n: t["section"] == n.get("section") and (t.get("variant") is None or t.get("variant") == n.get("variant"))
        i = 0
        for j, n in enumerate(spec["nodes"]):
            if not isinstance(n, dict):
                continue
            if i > 0 and T[i - 1].get("repeatable") and match(T[i - 1], n):
                continue
            k = next((x for x in range(i, len(T)) if match(T[x], n)), None)
            if k is None:
                if any(match(t, n) for t in T):
                    err("TEMPLATE_SEQUENCE", f"$.nodes[{j}]", f"{n.get('section')}/{n.get('variant')} is out of the order of template {tid!r}")
                else:
                    err("TEMPLATE_EXTRA_SECTION", f"$.nodes[{j}]", f"{n.get('section')}/{n.get('variant')} is not part of template {tid!r}")
                continue
            for t in T[i:k]:
                if t["required"]:
                    err("TEMPLATE_REQUIRED_MISSING", f"$.nodes[{j}]", f"required {t['section']}/{t.get('variant')} missing before {n.get('section')}")
            i = k + 1
        for t in T[i:]:
            if t["required"]:
                err("TEMPLATE_REQUIRED_MISSING", "$.nodes", f"required {t['section']}/{t.get('variant')} missing at end")
        # 3. routes
        if mode == "reference" and route not in tpl["routes"]:
            err("ROUTE_NOT_IN_TEMPLATE", "$.route", f"{route!r} is not a route of template {tid!r}")
        if mode == "generated" and not re.match(tpl["routePattern"], route):
            err("ROUTE_PATTERN", "$.route", f"{route!r} does not match {tpl['routePattern']}")

    C = lambda n: repo.contracts[n["section"]]
    cat = lambda n: C(n)["semantic"]["category"]
    positional = [n for n in nodes if not C(n)["constraints"].get("positionFixed")]

    # 4. graph rules
    heroes = [n for n in nodes if cat(n) == "HERO"]
    heroless = repo.graph["rules"]["ONE_HERO"]["exceptions"]["heroless templates"]
    if len(heroes) > 1:
        err("ONE_HERO", "$.nodes", f"{len(heroes)} HERO nodes")
    if tid in heroless and heroes:
        err("ONE_HERO", "$.nodes", f"template {tid!r} is heroless")
    if tid and tid not in heroless and tpl and not heroes:
        err("ONE_HERO", "$.nodes", f"template {tid!r} needs exactly one HERO")
    if heroes and positional and positional[0] is not heroes[0]:
        err("HERO_FIRST_IN_FLOW", "$.nodes", f"first in-flow node is {positional[0]['section']}, not the HERO")
    footers = [k for k, n in enumerate(positional) if n["section"] == "shell.footer"]
    if footers and footers[-1] != len(positional) - 1:
        err("FOOTER_LAST", "$.nodes", "shell.footer is not the last in-flow node")
    for k, n in enumerate(positional):
        if C(n)["constraints"].get("mustPrecedeFooter") and footers and (k + 1 >= len(positional) or positional[k + 1]["section"] != "shell.footer"):
            err("CTA_BEFORE_FOOTER", "$.nodes", f"{n['section']} must sit directly before shell.footer")
    counts, pair_counts = {}, {}
    for n in nodes:
        counts[n["section"]] = counts.get(n["section"], 0) + 1
        key = (n["section"], n.get("variant"))
        pair_counts[key] = pair_counts.get(key, 0) + 1
    for sid, cnt in counts.items():
        cons = repo.contracts[sid]["constraints"]
        if cons.get("onePerPage") and cnt > 1:
            err("ONE_PER_PAGE", "$.nodes", f"{sid} appears {cnt}x (onePerPage)")
        if cons.get("maxPerPage") and cnt > cons["maxPerPage"]:
            err("ONE_PER_PAGE", "$.nodes", f"{sid} appears {cnt}x (maxPerPage {cons['maxPerPage']})")
    for (sid, var), cnt in pair_counts.items():
        if var is not None and cnt > 1:
            err("ONE_PER_PAGE", "$.nodes", f"{sid}/{var} appears {cnt}x")
    for a, b in zip(nodes, nodes[1:]):
        if (a["section"], a.get("variant")) == (b["section"], b.get("variant")):
            err("NO_CONSECUTIVE_SAME_VARIANT", "$.nodes", f"{a['section']}/{a.get('variant')} twice in a row")
    exc = repo.graph["rules"]["NO_ADJACENT_SAME_CATEGORY"]["exceptions"]
    for a, b in zip(positional, positional[1:]):
        if cat(a) == cat(b) and f"{a['section']}->{b['section']}" not in exc:
            err("NO_ADJACENT_SAME_CATEGORY", "$.nodes", f"{a['section']} -> {b['section']} both {cat(a)}", "warn")
    secs = [n["section"] for n in nodes]
    if "chapter.body" in secs and ("chapter.header" not in secs or secs.index("chapter.header") > secs.index("chapter.body")):
        err("CHAPTER_HEADER_BEFORE_BODY", "$.nodes", "chapter.body needs chapter.header before it")
    for j, n in enumerate(nodes):
        if C(n)["constraints"].get("homeRouteOnly") and route != "/":
            err("HOME_ROUTE_ONLY", f"$.nodes[{j}]", f"{n['section']} is only allowed on '/'")
        if "retrievalEligible" in n:
            if n["section"] in RETRIEVAL_INELIGIBLE and n["retrievalEligible"] is not False:
                err("RUNTIME_NOT_RETRIEVABLE", f"$.nodes[{j}].retrievalEligible", f"{n['section']} is pinned retrievalEligible:false")
            if n["section"] not in RETRIEVAL_INELIGIBLE and n["retrievalEligible"] is False:
                err("RUNTIME_NOT_RETRIEVABLE", f"$.nodes[{j}].retrievalEligible", f"content section {n['section']} cannot be marked ineligible")
    looping = sum(1 for n in nodes if isinstance(n.get("motion"), dict) and n["motion"].get("pattern") in LOOPING_PATTERNS)
    if looping > MOTION_BUDGET_MAX_LOOPING:
        err("MOTION_BUDGET", "$.nodes", f"{looping} looping motion nodes (max {MOTION_BUDGET_MAX_LOOPING})", "warn")

    # 5. word budgets (walk the content contract)
    def budget(schema, value, path):
        if not isinstance(schema, dict):
            return
        if "$ref" in schema:
            schema = repo.schema["definitions"][schema["$ref"].split("/")[-1]]
        if isinstance(value, str) and "maxWords" in schema and wc(value) > schema["maxWords"]:
            err("MAX_WORDS", path, f"{wc(value)} words > maxWords {schema['maxWords']}")
        if isinstance(value, list):
            if "maxWordsTotal" in schema:
                total = sum(wc(s) for _, s in strings(value))
                if total > schema["maxWordsTotal"]:
                    err("MAX_WORDS_TOTAL", path, f"{total} words > maxWordsTotal {schema['maxWordsTotal']}")
            for i, v in enumerate(value):
                budget(schema.get("items", {}), v, f"{path}[{i}]")
        if isinstance(value, dict):
            for k, v in value.items():
                budget(schema.get("properties", {}).get(k, {}), v, f"{path}.{k}")
    budget(repo.schema["properties"]["meta"], spec.get("meta"), "$.meta")
    for j, n in enumerate(spec["nodes"]):
        if isinstance(n, dict) and n.get("section") in repo.contracts:
            budget({"$ref": f"#/definitions/content.{n['section']}"}, n.get("content"), f"$.nodes[{j}].content")
            for a_i, a in enumerate(n.get("assets") or []):
                if isinstance(a, dict) and isinstance(a.get("alt"), str) and wc(a["alt"]) > 20:
                    err("MAX_WORDS", f"$.nodes[{j}].assets[{a_i}].alt", "alt > 20 words")

    # 6. motion
    for j, n in enumerate(nodes):
        m = n.get("motion")
        if not isinstance(m, dict):
            err("MOTION_FALLBACK_MISSING", f"$.nodes[{j}].motion", "motion object missing")
            continue
        p = m.get("pattern")
        if p not in C(n)["motion"]["allowedPatterns"]:
            err("MOTION_PATTERN_NOT_ALLOWED", f"$.nodes[{j}].motion.pattern", f"{p!r} not allowed for {n['section']}")
        if "reducedMotionFallback" not in m:
            err("MOTION_FALLBACK_MISSING", f"$.nodes[{j}].motion", "reducedMotionFallback missing")
        elif p in repo.motion and m["reducedMotionFallback"] not in repo.motion[p]["fallbacks"]:
            err("MOTION_FALLBACK_MISMATCH", f"$.nodes[{j}].motion", f"{m['reducedMotionFallback']!r} is not a fallback of {p!r}")
        if p in repo.motion and m.get("trigger") not in repo.motion[p]["trigger"]:
            err("MOTION_TRIGGER_MISMATCH", f"$.nodes[{j}].motion.trigger", f"{m.get('trigger')!r} not a trigger of {p!r}")
        for f, catkey in (("durationToken", "motionDuration"), ("easingToken", "motionEasing")):
            if f in m and m[f] not in repo.catalog[catkey]:
                err("TOKEN_UNKNOWN", f"$.nodes[{j}].motion.{f}", f"{m[f]!r} not in token catalog")

    # 7. assets
    for j, n in enumerate(nodes):
        slots = C(n)["assetSlots"]
        used = {}
        for a_i, a in enumerate(n.get("assets") or []):
            if not isinstance(a, dict):
                continue
            path = f"$.nodes[{j}].assets[{a_i}]"
            slot = slots.get(a.get("slot"))
            if slot is None:
                err("ASSET_SLOT_UNKNOWN", path, f"slot {a.get('slot')!r} not defined for {n['section']}")
                continue
            used[a["slot"]] = used.get(a["slot"], 0) + 1
            allowed = slot["generatedRoles"] if mode == "generated" else slot["referenceRoles"] + slot["generatedRoles"]
            if a.get("role") not in allowed:
                err("ASSET_ROLE_NOT_ALLOWED", path, f"role {a.get('role')!r} not allowed in slot {a['slot']} ({mode})")
            if mode == "generated" and PINNED_AVAILABILITY.get(a.get("role")) != "generation-safe":
                err("GENERATED_MODE_ASSET", path, f"role {a.get('role')!r} is {PINNED_AVAILABILITY.get(a.get('role'))} (pinned)")
        for s_id, s in slots.items():
            if not (s["minItems"] <= used.get(s_id, 0) <= s["maxItems"]):
                err("ASSET_SLOT_COUNT", f"$.nodes[{j}].assets", f"slot {s_id}: {used.get(s_id, 0)} items, expected {s['minItems']}..{s['maxItems']}")

    # 8. generated-mode leakage (R2)
    if mode == "generated":
        P = repo.patterns
        groups = [("brand", "GENERATED_MODE_BRAND"), ("person", "GENERATED_MODE_PERSON"), ("url", "GENERATED_MODE_URL"), ("store", "GENERATED_MODE_STORE"),
                  ("cta", "GENERATED_MODE_CTA"), ("copy", "GENERATED_MODE_COPY"), ("statistic", "GENERATED_MODE_STATISTIC"), ("asset", "GENERATED_MODE_ASSET")]
        n_sh, corpus = repo.corpus
        for path, s in strings(spec):
            t = norm(s)
            for g, rule in groups:
                for pat in P[g]["patterns"]:
                    hit = re.search(r"(^|[/\s\"'(])" + re.escape(norm(pat).lstrip("/")), t) if g == "asset" else norm(pat) in t
                    if hit:
                        err(rule, path, f"contains source {g} pattern {pat!r}")
            for host in re.findall(r"(?:https?:)?//([^/\s\"'?#:]+)", s) + re.findall(r"\bwww\.([^/\s\"'?#:]+)", s):
                if not host.lower().endswith(RESERVED_HOST_SUFFIXES):
                    err("GENERATED_MODE_URL", path, f"host {host!r} is not a reserved .example/.invalid domain")
            w = words(t)
            for i in range(len(w) - n_sh + 1):
                if tuple(w[i:i + n_sh]) in corpus:
                    err("GENERATED_MODE_COPY", path, f"shares a {n_sh}-word run with source copy: {' '.join(w[i:i + n_sh])!r}")
                    break
        if spec.get("fontLicence") != "licensed-by-deployer":
            for j, n in enumerate(nodes):
                f = (n.get("style") or {}).get("fontFamily")
                if f in ("font.text", "font.display"):
                    err("GENERATED_MODE_FONT_LICENCE", f"$.nodes[{j}].style.fontFamily", f"{f} (Founders Grotesk, commercial) needs fontLicence 'licensed-by-deployer'; use font.fallback-sans")

    # 9. token policy (R10)
    fields = repo.policy["styleFields"]
    theme_tokens = set(repo.theme["resolved"])
    pairs = {tuple(p) for p in repo.policy["themes"].get(spec.get("theme"), {}).get("allowedPairs", [])}
    for j, n in enumerate(nodes):
        st = n.get("style")
        if not isinstance(st, dict):
            continue
        for f, v in st.items():
            path = f"$.nodes[{j}].style.{f}"
            if f not in fields or not isinstance(v, str):
                continue
            spec_f = fields[f]
            vl = v.strip().lower()
            if re.match(r"^(#[0-9a-f]{3,8}|rgba?\(|hsla?\()", vl) or vl in CSS_NAMED_COLORS:
                err("TOKEN_RAW_COLOR", path, f"raw colour {v!r}; use a {spec_f['prefix']}* token")
                continue
            if re.match(r"^-?[0-9.]+(px|rem|em|%|vh|vw)?$", vl):
                err("TOKEN_ARBITRARY_SPACING", path, f"raw value {v!r}; use a space.* token")
                continue
            if f == "fontFamily" and v not in repo.policy["fonts"]["supported"]:
                err("TOKEN_UNSUPPORTED_FONT", path, f"{v!r} is not a supported font token {repo.policy['fonts']['supported']}")
                continue
            if v not in repo.all_tokens:
                err("TOKEN_UNKNOWN", path, f"{v!r} is not in tokens/llm/token-catalog.json")
                continue
            if not v.startswith(spec_f["prefix"]) or v not in repo.catalog[spec_f["catalogKey"]]:
                err("TOKEN_WRONG_CATEGORY", path, f"{v!r} is not a {spec_f['prefix']}* token")
                continue
            if spec_f["catalogKey"] == "semanticColor" and v not in theme_tokens:
                err("TOKEN_NOT_IN_THEME", path, f"{v!r} not resolved by theme {spec.get('theme')!r}")
        if isinstance(st.get("surface"), str) and isinstance(st.get("text"), str) and (st["surface"], st["text"]) not in pairs:
            err("TOKEN_INVALID_COMBINATION", f"$.nodes[{j}].style", f"{st['surface']} + {st['text']} is not an allowed pair in theme {spec.get('theme')!r}")
    return out


def main(argv):
    files = sorted((ROOT / "schema/examples").glob("*.json")) if argv[1:] == ["--examples"] else [Path(a) for a in argv[1:]]
    if not files:
        print(__doc__); return 2
    bad = 0
    for f in files:
        res = validate(json.loads(Path(f).read_text()))
        errs = [r for r in res if r["severity"] == "error"]
        warns = [r for r in res if r["severity"] == "warn"]
        print(f"{'FAIL' if errs else 'ok  '}  {Path(f).name}: {len(errs)} error(s), {len(warns)} warning(s)")
        for r in res:
            print(f"      {r['severity']:5} {r['rule']:28} {r['path']}: {r['message']}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
