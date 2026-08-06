#!/usr/bin/env python3
"""Parse the live observation JSON into round cadence + py-spy stacks."""
import json

d = json.load(open("_perf_cse_live_out.json", encoding="utf-8"))
prev = {}
print("== round cadence ==")
for s in d["samples"]:
    for r in s["res"]:
        if "res" not in r:
            continue
        key = r["res"]
        cur = (r["n_trials"], r["mtime"], r["sum_total_ms"],
               str(r["last_round"]))
        if key not in prev:
            print(f"{key} start n={cur[0]} last={cur[3]}")
        elif prev[key][0] != cur[0]:
            dt = cur[1] - prev[key][1]
            din = (cur[2] - prev[key][2]) / 1000.0
            print(f"{key} n {prev[key][0]}->{cur[0]} wall_dt={dt:.1f}s "
                  f"in_round_dt={din:.1f}s last={cur[3]}")
        prev[key] = cur

print()
print("== pyspy dumps ==")
for p in d["pyspy"]:
    print("--- pid", p["pid"], "t=%.0f" % p["t"])
    print(p["dump"][:2400])
    print()
