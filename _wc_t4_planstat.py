# -*- coding: utf-8 -*-
import json, collections

plan = json.load(open("_wc_local/plan.json", encoding="utf-8"))
inv = json.load(open("_wc_local/_wc_witness_inventory.json", encoding="utf-8"))

print("protocol:", json.dumps(plan["protocol"], ensure_ascii=False))
ctrl = plan["control_cells"]; conf = plan["confirm_cells"]
print("control cells:", len(ctrl), " confirm cells:", len(conf),
      " skipped:", len(plan["skipped_witnesses"]))
print("skipped:", json.dumps(plan["skipped_witnesses"], ensure_ascii=False)[:1500])

print("\ninventory records:", len(inv))
print("by stage:", collections.Counter(r["stage"] for r in inv))
print("inv keys sample:", list(inv[0].keys()))
print("sample rec:", json.dumps(inv[0], ensure_ascii=False)[:900])

print("\ncontrol by stage:", collections.Counter(c["stage"] for c in ctrl))
print("confirm by stage:", collections.Counter(c["stage"] for c in conf))
print("control kernels:", len(set(c["kernel"] for c in ctrl)))
print("confirm rounds total:", sum(c["rounds"] for c in conf))

# distribution of confirm rounds
rr = sorted(c["rounds"] for c in conf)
print("confirm rounds min/med/max:", rr[0], rr[len(rr)//2], rr[-1])

# random vs stress witnesses
print("witness round_type:", collections.Counter(
    (r.get("divergence") or {}).get("round_type") for r in inv))

# fault classes
print("cse fault classes:", collections.Counter(
    r["fault_class"] for r in inv if r["stage"] == "cse"))
print("equiv fault classes:", collections.Counter(
    r["fault_class"] for r in inv if r["stage"] == "equiv"))
print("cse probes:", sorted(r["probe_id"] for r in inv if r["stage"] == "cse"))
