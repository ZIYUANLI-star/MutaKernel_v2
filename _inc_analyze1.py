"""Local analysis pass 1 over _inc_inventory_report.json: per-file counts,
dedup by probe_id, regrade-dryrun outcomes, reconciliation summary."""
import json
from collections import Counter, defaultdict

rep = json.load(open("_inc_inventory_report.json", encoding="utf-8"))

print("== files ==")
for name, meta in rep["files"].items():
    print(f"  {name}: lines={meta['lines']} inc={meta['inconclusive']}")

print("\n== inconclusive by (file, class) ==")
cnt = Counter((r["file"], str(r["inconclusive_class"]))
              for r in rep["inconclusive"])
for k, v in sorted(cnt.items()):
    print(f"  {k}: {v}")

by_probe = defaultdict(list)
for r in rep["inconclusive"]:
    by_probe[r["probe_id"]].append(r["file"])
multi = {p: fs for p, fs in by_probe.items() if len(fs) > 1}
print(f"\nunique probes with INC: {len(by_probe)}; in >1 file: {len(multi)}")
for p, fs in sorted(multi.items())[:10]:
    print("  ", p, fs)

print("\n== regrade dryrun outcomes (cse records only) ==")
cnt2 = Counter((r["file"], r.get("regrade_dryrun", {}).get("outcome", "n/a"))
               for r in rep["inconclusive"] if r["phase"] == "cse")
for k, v in sorted(cnt2.items()):
    print(f"  {k}: {v}")

print("\n== reconcile ==")
rc = rep["reconcile"]
for k in ("lane0_targets", "done", "pending", "sum_check_206",
          "pending_not_covered_by_345", "lane_pending_counts",
          "completed_files", "dup_probe_ids_across_active_obs",
          "global_targets_all_lanes"):
    print(f"  {k}: {rc[k]}")
print("  plan_lane_meta:")
for m in rc["plan_lane_meta"]:
    print("   ", m)
print("  archived_probe_status:")
for name, entries in rc["archived_probe_status"].items():
    st = Counter((e["in_done_union"], e["in_pending_345"], e["lane"])
                 for e in entries)
    print(f"    {name}: n={len(entries)} (done,pending345,lane)->count {dict(st)}")

print("\n== guard ==")
g = rep["guard"]
print("  pid:", g["pid"], "alive:", g["pid_alive"])
print("  done_markers:", g["done_markers"])
print("  ps:")
for l in g["ps"]:
    print("   ", l[:150])
print("  log_tail:")
for l in (g["log_tail"] or [])[-8:]:
    print("   ", l[:200])
print("\n== manifests 3/4/5 ==")
for k, v in rep["manifests"].items():
    print(f"  lane{k}: timeout_s={v['timeout_s']} round_timeout_s={v['round_timeout_s']} run_id={v['run_id']}")
    print(f"    partial={v['partial_evidence_thresholds']}")
    print(f"    resource={v['resource_degraded_thresholds'] and 'present'}")
