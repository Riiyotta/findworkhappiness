#!/usr/bin/env python3
"""Compute the design-policy content hash (R15).

    python3 extraction/policy_hash.py [repo-root]

sha256 over the files the policy is enforced by, in this fixed order, each prefixed by its
relative path and a NUL byte. registry.manifest.json designPolicy.contentHash must equal the
output; verify_all.py recomputes it and fails on drift.
"""
import hashlib, os, sys
from pathlib import Path

ENFORCED_BY = ["tokens/llm/token-policy.json", "compatibility/graph.json", "schema/pagespec.schema.json", "schema/semantic_validate.py"]

def policy_hash(root):
    h = hashlib.sha256()
    for rel in ENFORCED_BY:
        h.update(rel.encode() + b"\0")
        h.update((Path(root) / rel).read_bytes())
    return "sha256:" + h.hexdigest()

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(policy_hash(root))
