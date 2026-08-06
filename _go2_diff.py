#!/usr/bin/env python3
"""Diff local snapshots vs fetched running versions."""
import difflib

for a, b in [("_dl_mutant_worker.py", "_rt_mutant_worker.py"),
             ("_dl_run_e1_cse_falsify.py", "_rt_run_e1_cse_falsify.py")]:
    la = open(a, encoding="utf-8").read().splitlines()
    lb = open(b, encoding="utf-8").read().splitlines()
    d = list(difflib.unified_diff(la, lb, a, b, lineterm="", n=2))
    print(f"==== {a} vs {b}: {'IDENTICAL' if not d else str(len(d)) + ' diff lines'}")
    print("\n".join(d[:120]))
