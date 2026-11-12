#!/usr/bin/env python3
"""Whole-page-wrapper quality gate (R9). Called by verify_all.py; also runnable alone.

    python3 extraction/wrapper_gate.py [repo-root]

Heights come from extraction/measured-values.json sectionHeights (measured by
extraction/measure_sections.mjs in headless Chromium at 1440x900, one route per template).
Thresholds are pinned HERE in code, not read from JSON:
  HERO > 1800px warn, > 3000px error unless whitelisted
  one in-flow section > 50% of its page warn, > 60% error unless whitelisted
  (pages with < 3 in-flow sections are skipped; SHELL and fixed/overlay nodes take no page height)
  missing measurement -> error; measured at the wrong viewport -> error
Whitelist entries ({section, route, reviewedBy, justification, maxHeightPx}) need a justification
>= 30 chars and a maxHeightPx >= the measured height; stale or over-cap entries fail; a whitelisted
hit still warns. An agent reviewer must say "agent attestation, not a human sign-off".
"""
import json, os, re, sys
from pathlib import Path

HERO_WARN_PX = 1800
HERO_FAIL_PX = 3000
SHARE_WARN = 0.50
SHARE_FAIL = 0.60
MIN_INFLOW_SECTIONS = 3
REQUIRED_VIEWPORT_WIDTH = 1440
AGENT_RE = re.compile(r"claude|agent|assistant|automated|bot", re.I)
AGENT_ATTESTATION = "agent attestation, not a human sign-off"


def run(root, measured=None, contracts=None, templates=None):
    root = Path(root)
    mv = measured if measured is not None else json.loads((root / "extraction/measured-values.json").read_text())
    if contracts is None:
        contracts = {p.stem: json.loads(p.read_text()) for p in (root / "sections").glob("*.json")}
    if templates is None:
        templates = json.loads((root / "templates/templates.json").read_text())["templates"]
    errors, warnings = [], []
    sh = mv.get("sectionHeights")
    if not sh:
        return ["WRAPPER_MISSING_MEASUREMENT: no sectionHeights in measured-values.json"], warnings
    if (sh.get("viewport") or {}).get("width") != REQUIRED_VIEWPORT_WIDTH:
        errors.append(f"WRAPPER_WRONG_VIEWPORT: sectionHeights measured at {sh.get('viewport')}, gate requires width {REQUIRED_VIEWPORT_WIDTH}")
    pages = sh.get("pages", {})
    wl = mv.get("wrapperGateWhitelist", [])
    for i, w in enumerate(wl):
        miss = [k for k in ("section", "route", "reviewedBy", "justification", "maxHeightPx") if not w.get(k)]
        if miss:
            errors.append(f"WRAPPER_WHITELIST_INVALID: entry {i} missing {miss}")
        if len(str(w.get("justification", ""))) < 30:
            errors.append(f"WRAPPER_WHITELIST_INVALID: entry {i} justification shorter than 30 chars")
        if AGENT_RE.search(str(w.get("reviewedBy", ""))) and AGENT_ATTESTATION not in str(w.get("reviewedBy")):
            errors.append(f"WRAPPER_WHITELIST_INVALID: entry {i} reviewedBy is an agent but does not say '{AGENT_ATTESTATION}'")
    def whitelisted(route, sid, h):
        for w in wl:
            if w.get("route") == route and w.get("section") == sid:
                if not isinstance(w.get("maxHeightPx"), (int, float)) or h > w["maxHeightPx"]:
                    errors.append(f"WRAPPER_WHITELIST_OVER_CAP: {route} {sid} {h}px > maxHeightPx {w.get('maxHeightPx')}")
                    return False
                return True
        return False
    hits = set()
    # every template's measured route, and every in-flow section of that template, must be measured
    for tid, t in templates.items():
        r = t.get("measuredRoute")
        if r not in pages:
            errors.append(f"WRAPPER_MISSING_MEASUREMENT: template {tid} has no measured page ({r})")
            continue
        got = {s["section"] for s in pages[r]["sections"]}
        for n in t["nodes"]:
            c = contracts.get(n["section"])
            if c and c.get("flow") == "in-flow" and n["section"] not in got:
                errors.append(f"WRAPPER_MISSING_MEASUREMENT: {n['section']} not measured on {r}")
    for route, p in pages.items():
        ph = p.get("pageHeightPx")
        if not isinstance(ph, (int, float)) or ph <= 0:
            errors.append(f"WRAPPER_MISSING_MEASUREMENT: {route} has no pageHeightPx")
            continue
        inflow = [s for s in p["sections"] if s.get("inFlow") and contracts.get(s["section"], {}).get("semantic", {}).get("category") != "SHELL"]
        for s in p["sections"]:
            c = contracts.get(s["section"], {})
            if not isinstance(s.get("heightPx"), (int, float)):
                errors.append(f"WRAPPER_MISSING_MEASUREMENT: {route} {s['section']} has no heightPx")
                continue
            if c.get("semantic", {}).get("category") == "HERO" and s["heightPx"] > HERO_WARN_PX:
                ok = whitelisted(route, s["section"], s["heightPx"])
                hits.add((route, s["section"]))
                if s["heightPx"] > HERO_FAIL_PX and not ok:
                    errors.append(f"WRAPPER_HERO_TOO_TALL: {route} {s['section']} {s['heightPx']}px > {HERO_FAIL_PX}")
                else:
                    warnings.append(f"WRAPPER_HERO_TALL: {route} {s['section']} {s['heightPx']}px > {HERO_WARN_PX}" + (" (whitelisted)" if ok else ""))
        if len(inflow) < MIN_INFLOW_SECTIONS:
            continue
        for s in inflow:
            share = s["heightPx"] / ph
            if share > SHARE_WARN:
                ok = whitelisted(route, s["section"], s["heightPx"])
                hits.add((route, s["section"]))
                if share > SHARE_FAIL and not ok:
                    errors.append(f"WRAPPER_MAJORITY_SHARE: {route} {s['section']} holds {share:.0%} of the page (> {SHARE_FAIL:.0%})")
                else:
                    warnings.append(f"WRAPPER_LARGE_SHARE: {route} {s['section']} holds {share:.0%} of the page" + (" (whitelisted)" if ok else ""))
    for w in wl:
        if (w.get("route"), w.get("section")) not in hits:
            errors.append(f"WRAPPER_WHITELIST_STALE: {w.get('route')} {w.get('section')} no longer exceeds a threshold; remove the entry")
    return errors, warnings


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    e, w = run(root)
    for x in e: print("FAIL", x)
    for x in w: print("WARN", x)
    print(f"wrapper gate: {len(e)} error(s), {len(w)} warning(s)")
    sys.exit(1 if e else 0)
