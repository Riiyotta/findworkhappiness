#!/usr/bin/env python3
"""Prove that every verify_all.py check (and every pin/gate) actually catches drift.

    python3 extraction/prove_drift.py          # exit 1 if any injection goes undetected

For each case: copy design-repo into a fresh OS temp dir, inject ONE fault, run
`verify_all.py --repo <copy>` and require (a) exit code 1 and (b) a FAIL line for the named check.
A clean scratch copy must pass first (otherwise every "catch" would be meaningless).
The real repo is never modified. Repo root is derived from __file__.
"""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def jedit(rel, fn):
    def e(d):
        p = d / rel; o = json.loads(p.read_text()); fn(o); p.write_text(json.dumps(o, indent=2, ensure_ascii=False) + "\n")
    return e
def tedit(rel, old, new, count=1):
    def e(d):
        p = d / rel; s = p.read_text()
        if old not in s: raise RuntimeError(f"injection anchor not found in {rel}: {old[:40]!r}")
        p.write_text(s.replace(old, new, count))
    return e
def multi(*fs):
    def e(d):
        for f in fs: f(d)
    return e
def first_cite(o):
    return o["evidence"][0]
def shift_cite(o, delta):
    c = o["evidence"][-1]; f, rng = c["cite"].rsplit(":", 1); a = int(rng.split("-")[0]); c["cite"] = f"{f}:{a + delta}"
def about_sec(o, sid):
    return next(x for x in o["sectionHeights"]["pages"]["/about"]["sections"] if x["section"] == sid)

CASES = [
    ("json", "broken JSON file", lambda d: (d / "sections/chapter.body.json").write_text("{ not json")),
    ("contracts", "source.id equals the semantic id", jedit("sections/chapter.body.json", lambda o: o["source"].update(id="chapter.body"))),
    ("contracts", "blocked role listed as generated asset role", jedit("sections/hero.book-intro.json", lambda o: o["generatedAssetRoles"].append("author.portrait"))),
    ("contracts", "contract schema violation (unknown category)", jedit("sections/chapter.pager.json", lambda o: o["semantic"].update(category="FEATURES"))),
    ("citations", "citation out of range", jedit("sections/chapter.header.json", lambda o: o["evidence"][-1].update(cite="extraction/evidence/computed-1440.json:99999"))),
    ("citations", "citation in range but wrong line", jedit("sections/chapter.header.json", lambda o: shift_cite(o, 1))),
    ("citations", "source tag no longer at cited line", jedit("sections/hero.book-intro.json", lambda o: o["source"].update(lines=str(int(o["source"]["lines"]) + 3)))),
    ("citations", "token evidence points at wrong line", jedit("tokens/00-foundation/color.json", lambda o: o["tokens"]["color.yellow"]["evidence"][0].update(cite="extraction/evidence/site.css:1"))),
    ("citations", "citation outside the package", jedit("extraction/measured-values.json", lambda o: o["citations"][0].update(cite="../site/index.html:1"))),
    ("allowlist-parity", "phantom section in allowlist", jedit("tokens/llm/component-allowlist.json", lambda o: o["sections"].update({"testimonial.grid": {"contentFields": [], "variants": [], "motionPatterns": ["none"], "assetSlots": [], "retrievalEligible": True}}))),
    ("allowlist-parity", "phantom primitive in allowlist", jedit("tokens/llm/component-allowlist.json", lambda o: o["primitives"].append("primitive.divider"))),
    ("allowlist-parity", "orphan contract (allowlist entry removed)", jedit("tokens/llm/component-allowlist.json", lambda o: o["sections"].pop("shell.footer"))),
    ("allowlist-parity", "allowlist content fields stale", jedit("tokens/llm/component-allowlist.json", lambda o: o["sections"]["chapter.header"]["contentFields"].append("subtitle"))),
    ("schema-sync", "schema budget edited without the contract", jedit("schema/pagespec.schema.json", lambda o: o["definitions"]["content.chapter.header"]["properties"]["headline"].update(maxWords=40))),
    ("templates", "route mapped twice", jedit("templates/templates.json", lambda o: o["templates"]["about"]["routes"].append("/explore"))),
    ("templates", "template references unknown section", jedit("templates/templates.json", lambda o: o["templates"]["chapter"]["nodes"].append({"section": "faq.list", "required": False, "repeatable": False}))),
    ("templates", "selector map out of sync", tedit("extraction/section-selectors.mjs", "'shell.footer':", "'shell.site-footer':")),
    ("counts", "manifest count hand-edited", jedit("registry.manifest.json", lambda o: o["counts"].update(sections=21))),
    ("counts", "README count stale", tedit("README.md", "<!--count:routes-->17", "<!--count:routes-->18")),
    ("versions", "allowlist version bumped alone", jedit("tokens/llm/component-allowlist.json", lambda o: o.update(version="1.1.0"))),
    ("versions", "manifest pageSpecVersion drift", jedit("registry.manifest.json", lambda o: o.update(pageSpecVersion="2.0.0"))),
    ("pins", "registry availability loosened", jedit("assets/asset-roles.json", lambda o: o["roles"]["brand.wordmark"].update(availability="generation-safe"))),
    ("pins", "pin removed from semantic_validate.py", tedit("schema/semantic_validate.py", '"author.signature": "blocked-for-generation",', "")),
    ("pins", "pin removed from verify_all.py", tedit("extraction/verify_all.py", '"author.signature": "blocked-for-generation",', "")),
    ("pins", "contract + allowlist flipped together", multi(jedit("sections/runtime.cursor.json", lambda o: o.update(retrievalEligible=True)), jedit("tokens/llm/component-allowlist.json", lambda o: o["sections"]["runtime.cursor"].update(retrievalEligible=True)))),
    ("pins", "runtime-looking section not pinned", jedit("sections/shell.bottom-menu.json", lambda o: o.update(title="Bottom overlay menu"))),
    ("pins", "retrieval pin removed from code", tedit("extraction/verify_all.py", '"runtime.preloader", "runtime.sound-gate"', '"runtime.sound-gate"')),
    ("graph-validator", "graph rule removed", jedit("compatibility/graph.json", lambda o: o["rules"].pop("FOOTER_LAST"))),
    ("graph-validator", "graph rule added without implementation", jedit("compatibility/graph.json", lambda o: o["rules"].update(NO_TWO_CTAS={"severity": "error", "description": "x"}))),
    ("graph-validator", "hero exception list wrong", jedit("compatibility/graph.json", lambda o: o["rules"]["ONE_HERO"]["exceptions"]["heroless templates"].append("about"))),
    ("token-catalog", "foundation colour changed, catalog not rebuilt", jedit("tokens/00-foundation/color.json", lambda o: o["tokens"]["color.yellow"].update(value="#ffe000"))),
    ("token-catalog", "catalog edited by hand", jedit("tokens/llm/token-catalog.json", lambda o: o["categories"]["spacing"].update({"space.13px": "13px"}))),
    ("token-catalog", "policy category key not a catalog key", jedit("tokens/llm/token-policy.json", lambda o: o["rawValueRestrictions"].update(typography="x"))),
    ("token-catalog", "theme resolves a wrong value", jedit("tokens/themes/light.json", lambda o: o["resolved"]["surface.accent"].update(value="#ffff00"))),
    ("policy", "enforced file edited (policy hash drift)", jedit("tokens/llm/token-policy.json", lambda o: o["themes"]["light"]["allowedPairs"].append(["surface.inverse", "text.primary"]))),
    ("policy", "validator edited (policy hash drift)", tedit("schema/semantic_validate.py", "MOTION_BUDGET_MAX_LOOPING = 2", "MOTION_BUDGET_MAX_LOOPING = 9")),
    ("policy", "approval self-ratified", jedit("policy/design-policy.json", lambda o: o["approval"].update(status="approved", architectureDecisionRecorded=True))),
    ("policy", "forbidden category wording in README", lambda d: (d / "README.md").write_text((d / "README.md").read_text() + "\nA " + "Saa" + "S product.\n")),
    ("evidence-pins", "evidence file hand-edited", lambda d: (d / "extraction/evidence/site.css").write_text((d / "extraction/evidence/site.css").read_text() + "/* edit */\n")),
    ("evidence-pins", "parity results hand-edited", jedit("extraction/evidence/parity-results.json", lambda o: o.update(average=0.99))),
    ("wrapper-gate", "HERO 3100px", jedit("extraction/measured-values.json", lambda o: about_sec(o, "hero.about-title").update(heightPx=3100))),
    ("wrapper-gate", "majority share", jedit("extraction/measured-values.json", lambda o: (about_sec(o, "content.about-book").update(heightPx=9000), o["sectionHeights"]["pages"]["/about"].update(pageHeightPx=13000)))),
    ("wrapper-gate", "whitelist without justification", jedit("extraction/measured-values.json", lambda o: (about_sec(o, "hero.about-title").update(heightPx=3100), o.update(wrapperGateWhitelist=[{"section": "hero.about-title", "route": "/about", "reviewedBy": "owner", "justification": "", "maxHeightPx": 3200}])))),
    ("wrapper-gate", "missing measurement", jedit("extraction/measured-values.json", lambda o: o["sectionHeights"]["pages"].pop("/chapter/one"))),
    ("wrapper-gate", "wrong viewport", jedit("extraction/measured-values.json", lambda o: o["sectionHeights"]["viewport"].update(width=1280))),
    ("examples", "example exceeds a word budget", jedit("schema/examples/generated.chapter.pagespec.json", lambda o: o["nodes"][3]["content"].update(headline=" ".join(["word"] * 20)))),
    ("examples", "example leaks the source brand", jedit("schema/examples/generated.about.pagespec.json", lambda o: o["meta"].update(title="About The Search for Work Happiness"))),
    ("examples", "generated family example removed", lambda d: (d / "schema/examples/generated.about.pagespec.json").unlink()),
    ("parity", "exception self-approved", jedit("extraction/measured-values.json", lambda o: o["parity"]["exceptions"].append({"instance": "/about|x|0", "cause": "a cause that is at least thirty characters", "status": "approved", "approvedBy": "build agent"}))),
    ("parity", "below-gate section without exception", jedit("extraction/measured-values.json", lambda o: o["parity"]["perSection"]["belowGate"].update({"/x|y|0": {"min": 0.5}}))),
    ("hygiene", "absolute machine path", lambda d: (d / "README.md").write_text((d / "README.md").read_text() + "\nsee " + "/" + "Users/someone/project\n")),
    ("hygiene", "production approved by hand", jedit("registry.manifest.json", lambda o: o.update(productionApproved=True))),
    ("hygiene", "entryPoint outside the package", jedit("registry.manifest.json", lambda o: o["entryPoints"].update(ia="../ia.json"))),
    ("hygiene", "junk file", lambda d: (d / "sections/.DS_Store").write_text("x")),
    ("hygiene", "IR file created", lambda d: (d / "ir").mkdir() or (d / "ir/page.ir.json").write_text("{}")),
]

def run_verify(d):
    p = subprocess.run([sys.executable, str(d / "extraction/verify_all.py"), "--repo", str(d)], capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr

def scratch():
    d = Path(tempfile.mkdtemp(prefix="drift-")) / "design-repo"
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return d

d = scratch()
code, out = run_verify(d)
shutil.rmtree(d.parent, ignore_errors=True)
if code != 0:
    print(out); print("prove_drift: the clean scratch copy does not pass verify_all; fix that first"); sys.exit(1)
print("ok    clean scratch copy passes verify_all")
missed = 0
for check, name, inject in CASES:
    d = scratch()
    try:
        inject(d)
        code, out = run_verify(d)
        caught = code == 1 and re.search(r"^FAIL\s+%s\s" % re.escape(check), out, re.M)
    finally:
        shutil.rmtree(d.parent, ignore_errors=True)
    print(f"{'ok   ' if caught else 'MISS '} [{check}] {name}")
    missed += not caught
print(f"\nprove_drift: {len(CASES) - missed}/{len(CASES)} injections caught" + (f", {missed} MISSED" if missed else ""))
sys.exit(1 if missed else 0)
