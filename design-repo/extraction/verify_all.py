#!/usr/bin/env python3
"""One-shot verification of this design-repo. Standard library + jsonschema only; no browser.

    python3 extraction/verify_all.py [--repo PATH]     # exit 1 on any FAIL

The repo root is derived from __file__ (or --repo, used by prove_drift.py on scratch copies).
Every check below is proven to catch drift by extraction/prove_drift.py, which injects a fault
into a scratch copy for each one and asserts this script fails with that check's name.

Checks
  json                 every *.json parses
  contracts            sections/* validate against schema/section-contract.schema.json; id/semantic/source rules
  citations            every {cite, needle} and source {file, lines, tag}: file exists, range within the file,
                       needle/tag present on the first cited line (tag-at-line); bare path:line strings range-checked
  allowlist-parity     component-allowlist <-> primitives/components/sections files, content fields, variants,
                       motion patterns, asset slots, node properties, style fields, asset roles
  schema-sync          PageSpec schema content definitions == contract content; enums == registries
  templates            every node references a contract; every route mapped exactly once; selector map == contracts
  counts               registry.manifest.json counts recomputed from disk
  versions             allowlistVersion / pageSpecVersion parity (machine-checked); examples carry the schema version
  pins                 PINNED_AVAILABILITY and RETRIEVAL_INELIGIBLE: verify_all == semantic_validate == registries
  graph-validator      compatibility/graph.json rule ids/severities == semantic_validate.GRAPH_RULES, each implemented
  token-catalog        tokens/llm/token-catalog.json rebuilt from the token files; token-policy/theme resolve
  policy               designPolicy.contentHash recomputed; approval left pending; no forbidden wording
  evidence-pins        sha256 of extraction/evidence/* == measured-values.json pins (no hand edits)
  sibling-sources      ../site pins (WARN when the sibling project is absent)
  wrapper-gate         extraction/wrapper_gate.py
  examples             every schema/examples/*.json passes Draft-07 + semantic validation; family coverage
  parity               parity results recorded; below-gate sections have human-pending exceptions; no self-approval
  hygiene              entryPoints inside the package, no absolute machine paths, no junk files, manifest flags
"""
import argparse, hashlib, importlib.util, json, re, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
ROOT = Path(ap.parse_args().repo).resolve()

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
EXPECTED_ROUTE_COUNT = 17
REQUIRED_GENERATED_FAMILIES = {"home", "article", "about"}
PARITY_GATE = 0.80

results = []
def rec(check, ok, msg, warn=False):
    results.append((check, "PASS" if ok else ("WARN" if warn else "FAIL"), msg))

def j(rel):
    return json.loads((ROOT / rel).read_text())

def import_module(rel, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

# ---------------------------------------------------------------- json
bad_json = []
for p in sorted(ROOT.rglob("*.json")):
    try:
        json.loads(p.read_text())
    except Exception as e:
        bad_json.append(f"{p.relative_to(ROOT)}: {e}")
rec("json", not bad_json, "all JSON parses" if not bad_json else bad_json[:3])
if bad_json:
    for c, r, m in results: print(f"{r:4}  {c:16} {m}")
    sys.exit(1)

manifest = j("registry.manifest.json")
allow = j("tokens/llm/component-allowlist.json")
roles = j("assets/asset-roles.json")["roles"]
schema = j("schema/pagespec.schema.json")
templates_doc = j("templates/templates.json")
templates = templates_doc["templates"]
graph = j("compatibility/graph.json")
mv = j("extraction/measured-values.json")
contracts = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "sections").glob("*.json"))}
sv = import_module("schema/semantic_validate.py", "semantic_validate")

# ---------------------------------------------------------------- contracts
from jsonschema import Draft7Validator
cs = Draft7Validator(j("schema/section-contract.schema.json"))
cerr = []
for sid, c in contracts.items():
    cerr += [f"{sid}: {e.message[:120]}" for e in cs.iter_errors(c)]
    if c.get("id") != sid or c.get("semantic", {}).get("id") != sid:
        cerr.append(f"{sid}: id / semantic.id must equal the file name")
    if c.get("source", {}).get("id") == sid:
        cerr.append(f"{sid}: source.id must not equal the contract id (provenance != taxonomy)")
    for r in c.get("generatedAssetRoles", []):
        if PINNED_AVAILABILITY.get(r) != "generation-safe":
            cerr.append(f"{sid}: generatedAssetRoles contains {r} ({PINNED_AVAILABILITY.get(r)})")
    if c.get("motion", {}).get("default", {}).get("pattern") not in c.get("motion", {}).get("allowedPatterns", []):
        cerr.append(f"{sid}: default motion pattern not in allowedPatterns")
    if c.get("semantic", {}).get("category") == "HERO" and not sid.startswith("hero."):
        cerr.append(f"{sid}: HERO category on a non-hero id")
for rid, r in roles.items():
    if r["availability"] != "generation-safe":
        subs = r.get("generationSafeSubstitutes") or []
        if not subs or any(PINNED_AVAILABILITY.get(s) != "generation-safe" for s in subs):
            cerr.append(f"role {rid}: needs generation-safe generationSafeSubstitutes")
rec("contracts", not cerr, f"{len(contracts)} contracts valid (closed schema, source/semantic split, generation-safe roles)" if not cerr else cerr[:4])

# ---------------------------------------------------------------- citations
cit_err, n_cit = [], 0
_cache = {}
def flines(rel):
    if rel not in _cache:
        p = ROOT / rel
        _cache[rel] = p.read_text().split("\n") if p.is_file() else None
    return _cache[rel]
def check_cite(where, ref, needle=None):
    global n_cit
    n_cit += 1
    m = re.match(r"^([A-Za-z0-9_./-]+):(\d+)(?:-(\d+))?$", ref)
    if not m:
        cit_err.append(f"{where}: malformed citation {ref!r}"); return
    rel, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
    if rel.startswith("..") or rel.startswith("/"):
        cit_err.append(f"{where}: citation outside the package {ref!r}"); return
    L = flines(rel)
    if L is None:
        cit_err.append(f"{where}: missing file {rel}"); return
    n = len(L) - (1 if L and L[-1] == "" else 0)
    if not (1 <= a <= b <= n):
        cit_err.append(f"{where}: {ref} out of range (file has {n} lines)"); return
    if needle is not None and needle not in L[a - 1]:
        cit_err.append(f"{where}: needle {needle[:50]!r} not on {rel}:{a}")
def walk(o, where):
    if isinstance(o, dict):
        if "cite" in o and isinstance(o["cite"], str):
            check_cite(where, o["cite"], o.get("needle"))
        if {"file", "lines", "tag"} <= set(o) and isinstance(o.get("lines"), str):
            check_cite(where + " (source tag-at-line)", f"{o['file']}:{o['lines']}", o["tag"])
        for k, v in o.items():
            if k not in ("cite",):
                walk(v, where)
    elif isinstance(o, list):
        for v in o: walk(v, where)
    elif isinstance(o, str) and re.match(r"^(extraction|tokens|sections|schema|templates)/[A-Za-z0-9_./-]+\.[a-z]+:\d+(-\d+)?$", o):
        check_cite(where, o)
for p in sorted(ROOT.rglob("*.json")):
    rel = str(p.relative_to(ROOT))
    if rel.startswith("extraction/evidence/"):
        continue
    walk(json.loads(p.read_text()), rel)
rec("citations", not cit_err, f"{n_cit} citations resolve; needle/tag present on the cited line" if not cit_err else cit_err[:4])

# ---------------------------------------------------------------- allowlist parity
ap_err = []
prim_files = {json.loads(p.read_text())["id"] for p in (ROOT / "primitives").glob("*.json")}
comp_files = {json.loads(p.read_text())["id"] for p in (ROOT / "components").glob("*.json")}
if set(allow["primitives"]) != prim_files: ap_err.append(f"primitives: allowlist-only {sorted(set(allow['primitives']) - prim_files)}, file-only {sorted(prim_files - set(allow['primitives']))}")
if set(allow["components"]) != comp_files: ap_err.append(f"components: allowlist-only {sorted(set(allow['components']) - comp_files)}, file-only {sorted(comp_files - set(allow['components']))}")
if set(allow["sections"]) != set(contracts): ap_err.append(f"sections: allowlist-only {sorted(set(allow['sections']) - set(contracts))}, file-only {sorted(set(contracts) - set(allow['sections']))}")
for sid, a in allow["sections"].items():
    c = contracts.get(sid)
    if not c: continue
    if sorted(c["content"]["properties"]) != a["contentFields"]: ap_err.append(f"{sid}: contentFields differ from contract")
    if (c["variants"] or []) != a["variants"]: ap_err.append(f"{sid}: variants differ")
    if c["motion"]["allowedPatterns"] != a["motionPatterns"]: ap_err.append(f"{sid}: motionPatterns differ")
    if sorted(c["assetSlots"]) != a["assetSlots"]: ap_err.append(f"{sid}: assetSlots differ")
    if c["retrievalEligible"] != a["retrievalEligible"]: ap_err.append(f"{sid}: retrievalEligible differs from contract")
node_props = sorted(schema["definitions"]["node"]["properties"])
if node_props != allow["nodeProperties"]: ap_err.append(f"nodeProperties {allow['nodeProperties']} != schema {node_props}")
if sorted(j("tokens/llm/token-policy.json")["styleFields"]) != allow["styleFields"]: ap_err.append("styleFields differ from token-policy")
if sorted(roles) != allow["assetRoles"]: ap_err.append("assetRoles differ from assets/asset-roles.json")
rec("allowlist-parity", not ap_err, f"{len(allow['sections'])} sections, {len(prim_files)} primitives, {len(comp_files)} components, node/style/role lists in parity" if not ap_err else ap_err[:4])

# ---------------------------------------------------------------- schema sync
ss_err = []
for sid, c in contracts.items():
    if schema["definitions"].get(f"content.{sid}") != c["content"]:
        ss_err.append(f"content.{sid} in pagespec schema != contract content")
if sorted(schema["definitions"]["node"]["properties"]["section"]["enum"]) != sorted(contracts): ss_err.append("node.section enum != contracts")
if sorted(schema["definitions"]["assetRole"]["enum"]) != sorted(roles): ss_err.append("assetRole enum != registry")
if sorted(schema["properties"]["template"]["enum"]) != sorted(templates): ss_err.append("template enum != templates.json")
if schema["properties"]["mode"].get("enum") != ["reference", "generated"] or "mode" not in schema["required"]: ss_err.append("mode must be a required closed enum reference|generated")
if schema["definitions"]["motion"].get("additionalProperties") is not False or "reducedMotionFallback" not in schema["definitions"]["motion"]["required"]: ss_err.append("motion object must be closed and require reducedMotionFallback")
rec("schema-sync", not ss_err, "PageSpec schema content/enum definitions match contracts and registries" if not ss_err else ss_err[:4])

# ---------------------------------------------------------------- templates / routes / selector map
t_err = []
route_owner = {}
for tid, t in templates.items():
    for n in t["nodes"]:
        if n["section"] not in contracts: t_err.append(f"{tid}: unknown section {n['section']}")
        if n.get("variant") and n["variant"] not in contracts.get(n["section"], {}).get("variants", []): t_err.append(f"{tid}: unknown variant {n['section']}/{n['variant']}")
    for r in t["routes"]:
        if r in route_owner: t_err.append(f"route {r} mapped twice ({route_owner[r]}, {tid})")
        route_owner[r] = tid
        if not re.match(t["routePattern"], r): t_err.append(f"{tid}: route {r} does not match its routePattern")
if route_owner != templates_doc["routes"]: t_err.append("routes map != union of template routes")
if len(route_owner) != EXPECTED_ROUTE_COUNT: t_err.append(f"{len(route_owner)} routes mapped, expected {EXPECTED_ROUTE_COUNT}")
sel_src = (ROOT / "extraction/section-selectors.mjs").read_text()
sel_ids = set(re.findall(r"^\s*'([a-z]+\.[a-z0-9-]+)':\s*\{", sel_src, re.M))
if sel_ids != set(contracts): t_err.append(f"section-selectors.mjs keys != contracts: {sorted(sel_ids ^ set(contracts))}")
rec("templates", not t_err, f"{len(templates)} templates, {len(route_owner)} routes each mapped once, selector map in sync" if not t_err else t_err[:4])

# ---------------------------------------------------------------- counts
catalog = j("tokens/llm/token-catalog.json")
examples = sorted((ROOT / "schema/examples").glob("*.json"))
real = {"sections": len(contracts), "templates": len(templates), "routes": len(route_owner), "primitives": len(list((ROOT / "primitives").glob("*.json"))),
        "components": len(list((ROOT / "components").glob("*.json"))), "assetRoles": len(roles), "tokens": sum(len(v) for v in catalog["categories"].values()),
        "examples": len(examples), "graphRules": len(graph["rules"]), "retrievalIneligibleSections": sum(1 for c in contracts.values() if c["retrievalEligible"] is False)}
diff = {k: (manifest["counts"].get(k), v) for k, v in real.items() if manifest["counts"].get(k) != v}
if sorted(manifest["counts"]) != sorted(real): diff["keys"] = (sorted(manifest["counts"]), sorted(real))
if sorted(manifest.get("examples", [])) != sorted(f"schema/examples/{p.name}" for p in examples): diff["examples-list"] = "manifest examples list != files"
readme = (ROOT / "README.md").read_text() if (ROOT / "README.md").exists() else ""
for k in ("sections", "templates", "routes", "assetRoles", "tokens"):
    m = re.search(r"<!--count:%s-->(\d+)" % k, readme)
    if not m or int(m.group(1)) != real[k]: diff[f"README:{k}"] = (m and m.group(1), real[k])
rec("counts", not diff, f"manifest + README counts recomputed: {real}" if not diff else f"drift (claimed, real): {diff}")

# ---------------------------------------------------------------- versions
v_err = []
if manifest.get("allowlistVersion") != allow.get("version"): v_err.append(f"allowlistVersion {manifest.get('allowlistVersion')} != allowlist {allow.get('version')}")
if manifest.get("pageSpecVersion") != schema["properties"]["pageSpecVersion"].get("const"): v_err.append("pageSpecVersion != schema const")
for p in examples:
    if json.loads(p.read_text()).get("pageSpecVersion") != manifest.get("pageSpecVersion"): v_err.append(f"{p.name}: pageSpecVersion drift")
if "versionFieldNote" not in manifest: v_err.append("manifest lacks versionFieldNote")
rec("versions", not v_err, f"allowlistVersion {allow.get('version')} and pageSpecVersion {manifest.get('pageSpecVersion')} in parity (repositoryVersion is documentation-only)" if not v_err else v_err)

# ---------------------------------------------------------------- pins
p_err = []
if PINNED_AVAILABILITY != sv.PINNED_AVAILABILITY: p_err.append(f"PINNED_AVAILABILITY differs between verify_all and semantic_validate: {sorted(set(PINNED_AVAILABILITY.items()) ^ set(sv.PINNED_AVAILABILITY.items()))[:3]}")
reg = {k: v["availability"] for k, v in roles.items()}
if reg != PINNED_AVAILABILITY: p_err.append(f"registry availability != pin: {sorted(set(reg.items()) ^ set(PINNED_AVAILABILITY.items()))[:3]}")
if RETRIEVAL_INELIGIBLE != sv.RETRIEVAL_INELIGIBLE: p_err.append("RETRIEVAL_INELIGIBLE differs between verify_all and semantic_validate")
for sid, c in contracts.items():
    pinned = sid in RETRIEVAL_INELIGIBLE
    if c["retrievalEligible"] is pinned: p_err.append(f"{sid}: contract retrievalEligible={c['retrievalEligible']} contradicts the pin")
    if allow["sections"].get(sid, {}).get("retrievalEligible") is pinned: p_err.append(f"{sid}: allowlist retrievalEligible contradicts the pin")
    if RUNTIME_NAME_RE.search(sid + " " + c["title"]) and not pinned: p_err.append(f"{sid}: looks like runtime/utility UI but is not pinned retrievalEligible:false")
    if not c["retrievalEligible"] and len(c.get("retrievalReason", "")) < 30: p_err.append(f"{sid}: retrievalReason < 30 chars")
for rid in ("brand.wordmark", "author.portrait", "author.signature", "audio.narration", "link.outbound", "link.download"):
    if roles.get(rid, {}).get("availability") == "generation-safe": p_err.append(f"{rid} must never be generation-safe")
rec("pins", not p_err, f"{len(PINNED_AVAILABILITY)} availability pins and {len(RETRIEVAL_INELIGIBLE)} retrieval pins agree across code, registry, contracts, allowlist" if not p_err else p_err[:4])

# ---------------------------------------------------------------- graph <-> validator
g_err = []
g = {k: v["severity"] for k, v in graph["rules"].items()}
if g != sv.GRAPH_RULES: g_err.append(f"graph {sorted(set(g.items()) ^ set(sv.GRAPH_RULES.items()))} differs from validator")
sv_src = (ROOT / "schema/semantic_validate.py").read_text()
for rid in g:
    if not re.search(r'err\("%s"' % rid, sv_src): g_err.append(f"{rid} has no implementation in semantic_validate.py")
heroless = set(graph["rules"]["ONE_HERO"]["exceptions"]["heroless templates"])
for tid, t in templates.items():
    has_hero = any(contracts[n["section"]]["semantic"]["category"] == "HERO" for n in t["nodes"] if n["section"] in contracts)
    if has_hero == (tid in heroless): g_err.append(f"ONE_HERO exception list disagrees with template {tid}")
rec("graph-validator", not g_err, f"{len(g)} graph rules == validator rules, each implemented; hero exceptions match templates" if not g_err else g_err[:4])

# ---------------------------------------------------------------- token catalog sync
k_err = []
F = lambda n: j(f"tokens/00-foundation/{n}.json")
col, typ, rad, spc, brk, ele, mot, pat = F("color"), F("typography"), F("radius"), F("spacing"), F("breakpoint"), F("elevation"), F("motion"), F("motion-patterns")
sem = j("tokens/10-semantic/semantic.json")["tokens"]
rebuilt = {
    "color": {k: v["value"] for k, v in col["tokens"].items()},
    "semanticColor": {k: col["tokens"][v["ref"]]["value"] for k, v in sem.items()},
    "fontFamily": {k: v["value"] for k, v in typ["fontFamily"].items()},
    "fontSize": {k: v["value"] for k, v in typ["fontSize"].items()},
    "lineHeight": {k: v["value"] for k, v in typ["lineHeight"].items()},
    "letterSpacing": {k: v["value"] for k, v in typ["letterSpacing"].items()},
    "radius": {k: v["value"] for k, v in rad["tokens"].items()},
    "spacing": {k: v["value"] for k, v in spc["tokens"].items()},
    "breakpoint": {k: v["value"] for k, v in brk["tokens"].items()},
    "elevation": {k: v["value"] for k, v in ele["tokens"].items()},
    "motionDuration": {k: v["value"] for k, v in mot["duration"].items()},
    "motionEasing": {k: v["value"] for k, v in mot["easing"].items()},
    "motionPattern": {k: v["description"] for k, v in pat["patterns"].items()},
}
for cat in sorted(set(rebuilt) | set(catalog["categories"])):
    if rebuilt.get(cat) != catalog["categories"].get(cat):
        a, b = rebuilt.get(cat) or {}, catalog["categories"].get(cat) or {}
        k_err.append(f"catalog.{cat} out of sync: {sorted(set(a.items()) ^ set(b.items()))[:2]}")
theme = j("tokens/themes/light.json")["resolved"]
for k, v in theme.items():
    if sem.get(k, {}).get("ref") != v["ref"] or col["tokens"].get(v["ref"], {}).get("value") != v["value"]: k_err.append(f"theme light: {k} does not resolve to its foundation value")
if set(theme) != set(sem): k_err.append("theme light does not resolve every semantic token")
pol = j("tokens/llm/token-policy.json")
for f, d in pol["styleFields"].items():
    if d["catalogKey"] not in catalog["categories"]: k_err.append(f"token-policy styleFields.{f}: catalogKey {d['catalogKey']} not in catalog")
for k in pol["rawValueRestrictions"]:
    if k not in catalog["categories"]: k_err.append(f"token-policy rawValueRestrictions key {k} not a catalog key")
for a, b in pol["themes"]["light"]["allowedPairs"]:
    if a not in theme or b not in theme: k_err.append(f"allowedPair {a}+{b} not in theme")
for f in pol["fonts"]["supported"]:
    if f not in catalog["categories"]["fontFamily"]: k_err.append(f"supported font {f} not in catalog")
for name, ctoks in (("component", j("tokens/20-component/component.json")["tokens"]),):
    for k, v in ctoks.items():
        if v["ref"] not in {t for c in catalog["categories"].values() for t in c}: k_err.append(f"{name} token {k} refs unknown {v['ref']}")
rec("token-catalog", not k_err, f"catalog rebuilt from token files: {sum(len(v) for v in rebuilt.values())} tokens in sync; policy/theme resolve" if not k_err else k_err[:4])

# ---------------------------------------------------------------- policy
po_err = []
ph = import_module("extraction/policy_hash.py", "policy_hash").policy_hash(ROOT)
dp = manifest.get("designPolicy", {})
if dp.get("contentHash") != ph: po_err.append(f"designPolicy.contentHash {dp.get('contentHash', '')[:19]} != recomputed {ph[:19]}")
policy = j("policy/design-policy.json")
if policy.get("policyId") != dp.get("policyId") or policy.get("policyVersion") != dp.get("policyVersion"): po_err.append("policy file id/version != manifest")
if dp.get("commonIrVersion") != "0.5" or dp.get("enforcementMode") != "hard-and-soft": po_err.append("commonIrVersion/enforcementMode")
if policy.get("approval", {}).get("status") != "defined-pending-architecture-review" or policy["approval"].get("architectureDecisionRecorded") is not False: po_err.append("approval must stay pending until the human owner records a decision")
if policy.get("classification", {}).get("category") != manifest.get("category"): po_err.append("category differs between manifest and policy")
blob = (readme + json.dumps(policy) + json.dumps(manifest)).lower()
if "saa" + "s" in blob: po_err.append("forbidden category wording present in README/policy/manifest")
if sorted(policy.get("enforcedBy", [])) != sorted(import_module("extraction/policy_hash.py", "ph2").ENFORCED_BY): po_err.append("policy.enforcedBy != hashed files")
rec("policy", not po_err, f"contentHash {ph[:23]}... matches; approval pending; category {manifest.get('category')}" if not po_err else po_err)

# ---------------------------------------------------------------- evidence pins
e_err = []
pins = mv.get("evidencePins", {})
ev_files = {f"extraction/evidence/{p.name}": p for p in (ROOT / "extraction/evidence").iterdir() if p.is_file() and p.name != "parity-results.json"}
if set(pins) != set(ev_files): e_err.append(f"evidence files != pins: {sorted(set(pins) ^ set(ev_files))}")
for rel, p in ev_files.items():
    if pins.get(rel) != "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest(): e_err.append(f"{rel} changed since it was pinned")
pr = ROOT / "extraction/evidence/parity-results.json"
ps = mv.get("parity", {}).get("perSection", {})
if pr.exists() and ps.get("sha256") != "sha256:" + hashlib.sha256(pr.read_bytes()).hexdigest(): e_err.append("parity-results.json changed since it was pinned")
rec("evidence-pins", not e_err, f"{len(ev_files)} evidence files match their sha256 pins" if not e_err else e_err[:4])

# ---------------------------------------------------------------- sibling sources (graceful)
sib = ROOT.parent
spins = mv.get("siblingSources", {}).get("pins", {})
if (sib / "site" / "index.html").exists():
    bad = [k for k, v in spins.items() if not (sib / k).exists() or "sha256:" + hashlib.sha256((sib / k).read_bytes()).hexdigest() != v]
    rec("sibling-sources", not bad, f"{len(spins)} mirrored source files match their pins" if not bad else f"source moved since extraction (R16: re-run extraction + build): {bad[:3]}")
else:
    rec("sibling-sources", False, "sibling source tree (../site) absent: pins not checked (standalone copy)", warn=True)

# ---------------------------------------------------------------- wrapper gate
wg = import_module("extraction/wrapper_gate.py", "wrapper_gate")
werr, wwarn = wg.run(ROOT)
rec("wrapper-gate", not werr, f"0 errors, {len(wwarn)} warnings (HERO {wg.HERO_WARN_PX}/{wg.HERO_FAIL_PX}px, share {wg.SHARE_WARN:.0%}/{wg.SHARE_FAIL:.0%})" if not werr else werr[:4])
for w in wwarn: rec("wrapper-gate", False, w, warn=True)

# ---------------------------------------------------------------- examples
x_err, fams, modes = [], set(), set()
for p in examples:
    spec = json.loads(p.read_text())
    res = [r for r in sv.validate(spec, ROOT) if r["severity"] == "error"]
    if res: x_err.append(f"{p.name}: {[(r['rule'], r['path']) for r in res[:3]]}")
    modes.add(spec.get("mode"))
    if spec.get("mode") == "generated" and spec.get("template") in templates: fams.add(templates[spec["template"]]["family"])
if "reference" not in modes: x_err.append("no reference example")
if not REQUIRED_GENERATED_FAMILIES <= fams: x_err.append(f"generated examples missing families {sorted(REQUIRED_GENERATED_FAMILIES - fams)}")
rec("examples", not x_err, f"{len(examples)} examples pass Draft-07 + semantic validation; generated families {sorted(fams)}" if not x_err else x_err[:4])

# ---------------------------------------------------------------- parity
pa_err = []
par = mv.get("parity", {})
if not par.get("screenLevel"): pa_err.append("screen-level parity numbers missing")
if not pr.exists() or "gate" not in ps: pa_err.append("per-section parity not recorded (run extraction/parity.mjs, then extraction/build_repo.py)")
exc = {e.get("instance"): e for e in par.get("exceptions", [])}
for k in (ps.get("belowGate") or {}):
    e = exc.get(k)
    if not e: pa_err.append(f"{k} below the {PARITY_GATE:.0%} gate without an exception entry")
for e in par.get("exceptions", []):
    if e.get("approvedBy") is not None or e.get("status") != "pending human approval": pa_err.append(f"exception {e.get('instance')} must stay 'pending human approval' with approvedBy null")
    if len(str(e.get("cause", ""))) < 30: pa_err.append(f"exception {e.get('instance')} needs a real cause")
rec("parity", not pa_err, f"per-section parity recorded (average {ps.get('average')}, {len(ps.get('belowGate') or {})} below gate, all pending human approval)" if not pa_err else pa_err[:4])

# ---------------------------------------------------------------- hygiene
h_err = []
for k, v in manifest.get("entryPoints", {}).items():
    if v.startswith("..") or v.startswith("/") or not (ROOT / v).exists(): h_err.append(f"entryPoint {k} -> {v} not inside the package")
USERS = "Users"  # split so this file itself never contains a machine-path literal
absre = re.compile("/" + USERS + r"/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+/|/private/(tmp|var)/|[A-Z]:\\\\" + USERS + r"\\\\")
for p in ROOT.rglob("*"):
    if p.is_file() and p.suffix in (".json", ".md", ".py", ".mjs", ".txt", ".css") and absre.search(p.read_text(errors="ignore")):
        h_err.append(f"absolute machine path in {p.relative_to(ROOT)}")
junk = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.name in (".DS_Store", "Thumbs.db") or "__MACOSX" in p.parts or p.suffix == ".png"]
if junk: h_err.append(f"junk/screenshot files: {junk[:3]}")
if manifest.get("status") != "design-review-pending" or manifest.get("productionApproved") is not False: h_err.append("manifest status must be design-review-pending, productionApproved false")
ir_files = [p for p in ROOT.rglob("*") if p.is_file() and (re.search(r"(^|[._-])ir([._-]|$)", p.stem.lower()) or "ir" in [x.lower() for x in p.relative_to(ROOT).parts[:-1]])]
if ir_files: h_err.append(f"IR file(s) present; this build must not create IR: {[str(p.relative_to(ROOT)) for p in ir_files][:3]}")
rec("hygiene", not h_err, "entryPoints inside, no absolute paths, no junk, approval flags unset" if not h_err else h_err[:4])

for c, r, m in results:
    print(f"{r:4}  {c:16} {m}")
fails = sum(1 for _, r, _ in results if r == "FAIL")
print(f"\nverify_all: {sum(1 for _, r, _ in results if r == 'PASS')} pass, {fails} fail, {sum(1 for _, r, _ in results if r == 'WARN')} warn")
sys.exit(1 if fails else 0)
