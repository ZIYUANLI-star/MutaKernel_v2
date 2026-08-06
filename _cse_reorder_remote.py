"""Remote-side: push oversubscription-risk kernels to the END of lane3's
execution queue (plan kernel order = execution order after the driver fix).

Risk set = PROVEN_UNSAFE (P39 measured 41.8GB, P21) + any lane3 kernel with
resource/OOM markers anywhere in the equiv/CSE history (>36.9GB attempted
under the 0.45 cap => assumed >40GB-risk while lane4/5 still run).
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")
RESOURCE_MARKER = "resource/infrastructure limit"
KNOWN_UNSAFE_TAIL = ["L1_P21", "L1_P39"]  # most dangerous absolutely last

HISTORY = [
    E1 / "equiv_observations.jsonl",
    E1 / "equiv_observations_lane0.jsonl",
    E1 / "equiv_observations_lane1.jsonl",
    E1 / "equiv_observations_lane2.jsonl",
    E1 / "equiv_observations_lane3.jsonl",
    E1 / "equiv_observations_lane4_requeue.jsonl",
    E1 / "equiv_observations_timeout_v1.jsonl",
    E1 / "equiv_observations_timeout_v2.jsonl",
    E1 / "cse_observations_lane0.jsonl",
    E1 / "cse_observations_lane0_timeout_v1.jsonl",
]

marker_counts = Counter()
for path in HISTORY:
    if not path.exists():
        continue
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        if RESOURCE_MARKER in line or '"out_of_memory"' in line:
            marker_counts[json.loads(line)["kernel"]] += 1

plan_path = E1 / "cse_lane_plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8"))
lane3 = plan["lanes"][3]
kernels = list(lane3["kernels"])

risky_scanned = [k for k in kernels
                 if marker_counts.get(k) and k not in KNOWN_UNSAFE_TAIL]
tail = risky_scanned + [k for k in KNOWN_UNSAFE_TAIL if k in kernels]
head = [k for k in kernels if k not in set(tail)]
new_order = head + tail
assert sorted(new_order) == sorted(kernels), "reorder must be a permutation"

lane3["kernels"] = new_order
lane3["queue_note"] = ("resource-risk kernels scheduled last so they run "
                       "after lanes 4/5 finish (oversubscription window)")
plan["version"] = 4
plan["v4_created_at"] = datetime.now(timezone.utc).isoformat()
plan_path.write_text(json.dumps(plan, indent=1), encoding="utf-8")

print("resource-marker counts per lane3 kernel:",
      {k: marker_counts[k] for k in kernels if marker_counts.get(k)})
print("tail (deferred):", tail)
print("new lane3 order:", new_order)
print("REORDER_OK")
