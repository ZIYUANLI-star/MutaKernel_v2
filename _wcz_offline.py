"""Offline structural analysis of the WC-1 plan + inventory (no SSH).

Answers ahead of the run: which fault classes exist, which control unit each
witness depends on, and whether _wc_analyze.py's control keying collides.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

D = Path("_wc_remote")
inv = json.loads((D / "_wc_witness_inventory.json").read_text(encoding="utf-8"))
plan = json.loads((D / "plan.json").read_text(encoding="utf-8"))
shortcut = json.loads((D / "_wc_seed_shortcut.json").read_text(encoding="utf-8"))

print("=== inventory ===")
print("records:", len(inv), "| keys:", sorted(inv[0].keys()))
print("stage:", dict(Counter(r["stage"] for r in inv)))
print("fault_class overall:", dict(Counter(r["fault_class"] for r in inv)))
for stage in ("cse", "equiv"):
    rows = [r for r in inv if r["stage"] == stage]
    print("  %-6s n=%d fault_classes=%s"
          % (stage, len(rows), dict(Counter(r["fault_class"] for r in rows))))

print("\n=== non-numeric (out of scope) witnesses ===")
for r in inv:
    d = r.get("divergence") or {}
    if d.get("round_type") is None:
        print("  [%s] %-34s %-10s %s" % (r["stage"], r["probe_id"],
                                         r["fault_class"], r.get("operator")))
print("skipped_witnesses in plan:", len(plan["skipped_witnesses"]))

print("\n=== fault class -> probes (per stage) ===")
byfc = defaultdict(list)
for r in inv:
    byfc[(r["stage"], r["fault_class"])].append(r)
for k in sorted(byfc):
    rows = byfc[k]
    print("  %-6s %-10s n=%2d" % (k[0], k[1], len(rows)))
    for r in rows:
        d = r.get("divergence") or {}
        print("        %-34s %-22s %s/%s/si%s/ri%s"
              % (r["probe_id"], r["operator"], d.get("round_type"),
                 d.get("policy"), d.get("sub_index"), d.get("round_index")))

print("\n=== control-key collisions in _wc_analyze.pos_key ===")
seen = defaultdict(list)
for c in plan["control_cells"]:
    for policy, si in c["positions"]:
        seen[(c["kernel"], c["stage"], str(policy))].append(c["cell_id"])
for k, v in sorted(seen.items()):
    if len(set(v)) > 1:
        print("  COLLISION", k, "->", sorted(set(v)))
print("  (no line above = no collision)")

print("\n=== seed shortcut ===")
sc = {k: bool(v.get("construction_seed_independent")) for k, v in shortcut.items()}
print("  shortcut True :", sorted(k for k, v in sc.items() if v))
print("  shortcut False:", sorted(k for k, v in sc.items() if not v))

print("\n=== control cells planned (61) ===")
for c in sorted(plan["control_cells"], key=lambda x: x["cell_id"]):
    print("  %-46s rounds=%-4d replays=%-3d probes=%s"
          % (c["cell_id"], c["rounds"], c["replays"],
             ",".join(c.get("probe_ids") or [])[:90]))

print("\n=== confirm cells planned (82) ===")
print(dict(Counter(c["stage"] for c in plan["confirm_cells"])))
