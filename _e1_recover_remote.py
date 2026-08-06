"""Remote-side: post-outage integrity check + full aggregation for E1 equiv.

1. Repair a possibly truncated last line in the requeue observations and
   reconcile its completed checkpoint (rebuilt from valid obs ids if needed).
2. Verify the global account (done + pending == 527) and list pending ids.
3. Aggregate: per-source counts/grades, overall distribution, WITNESSED
   breakdowns, requeue-lane stats, and the before/after fate of the 57
   archived timeout INCONCLUSIVEs.
"""
import json
import statistics
from collections import Counter
from pathlib import Path

E1 = Path("/root/mk_v2_runs/e1")

# ---------------------------------------------------------------- integrity
obs_path = E1 / "equiv_observations_lane4_requeue.jsonl"
done_path = E1 / "equiv_completed_lane4_requeue.json"

raw_lines = open(obs_path, encoding="utf-8").read().splitlines(keepends=True)
valid_lines, valid_ids, truncated = [], [], []
for i, line in enumerate(raw_lines):
    if not line.strip():
        continue
    try:
        row = json.loads(line)
        valid_lines.append(line if line.endswith("\n") else line + "\n")
        valid_ids.append(row["probe_id"])
    except Exception:
        truncated.append((i, line[:120]))

if truncated:
    print(f"TRUNCATED lines found: {[(i, s) for i, s in truncated]}")
    with open(obs_path, "w", encoding="utf-8") as fh:
        fh.writelines(valid_lines)
    print(f"rewrote obs with {len(valid_lines)} valid lines")
else:
    print(f"obs intact: {len(valid_lines)} valid lines, no truncation")

try:
    completed = set(json.load(open(done_path)))
    completed_ok = True
except Exception as exc:
    completed = set()
    completed_ok = False
    print(f"completed file unreadable ({exc}); will rebuild")

if not completed_ok or completed != set(valid_ids):
    print(f"reconcile completed: file={len(completed)} obs={len(valid_ids)} "
          f"only_in_completed={sorted(completed - set(valid_ids))} "
          f"only_in_obs={sorted(set(valid_ids) - completed)}")
    done_path.write_text(json.dumps(sorted(set(valid_ids))))
    completed = set(valid_ids)
    print("completed rebuilt from valid obs ids")
else:
    print(f"completed consistent: {len(completed)} ids == obs lines")

# ---------------------------------------------------------------- account
survivors_by_kernel = {}
for line in open(E1 / "baseline_observations.jsonl", encoding="utf-8"):
    row = json.loads(line)
    if row.get("status") == "survived":
        survivors_by_kernel.setdefault(row["kernel"], []).append(row["probe_id"])
all_survivors = {p for pids in survivors_by_kernel.values() for p in pids}

SOURCES = [
    ("pre-switch", E1 / "equiv_observations.jsonl"),
    ("lane0", E1 / "equiv_observations_lane0.jsonl"),
    ("lane1", E1 / "equiv_observations_lane1.jsonl"),
    ("lane2", E1 / "equiv_observations_lane2.jsonl"),
    ("lane3", E1 / "equiv_observations_lane3.jsonl"),
    ("lane4_requeue", obs_path),
]
rows_by_source = {}
for name, path in SOURCES:
    rows_by_source[name] = [json.loads(l) for l in open(path, encoding="utf-8")
                            if l.strip()] if path.exists() else []

all_rows = [r for rows in rows_by_source.values() for r in rows]
done_ids = [r["probe_id"] for r in all_rows]
dupes = [pid for pid, n in Counter(done_ids).items() if n > 1]
pending = sorted(all_survivors - set(done_ids))
print(f"\nACCOUNT: done={len(done_ids)} dupes={dupes} pending={len(pending)} "
      f"sum={len(done_ids) + len(pending)} (expect 527)")
print("pending ids:", pending)

# ---------------------------------------------------------------- aggregate
print("\n== per-source ==")
for name, _ in SOURCES:
    rows = rows_by_source[name]
    print(f"{name}: n={len(rows)} "
          f"{dict(Counter(r['evidence_grade'] for r in rows))}")

print("\n== overall graded ==")
print(dict(Counter(r["evidence_grade"] for r in all_rows)))

wit = [r for r in all_rows if r["evidence_grade"] == "WITNESSED_NON_EQUIVALENT"]
print("\n== witnessed breakdown ==")
print("by fault_class:", dict(Counter(r.get("fault_class") or "?" for r in wit)))
pol = Counter()
for r in wit:
    div = r.get("divergence") or {}
    pol[str(div.get("policy"))] += 1
print("by trigger policy (None=random round):", dict(pol))
print("by kernel top10:",
      Counter(r["kernel"] for r in wit).most_common(10))

rq = rows_by_source["lane4_requeue"]
print("\n== requeue lane ==")
print("grades:", dict(Counter(r["evidence_grade"] for r in rq)))
print("budget_exhausted:",
      sum(1 for r in rq if (r.get("evidence") or {}).get("budget_exhausted")))
walls = sorted(r["wall_ms"] / 1000 for r in rq)
if walls:
    print(f"wall_s median={statistics.median(walls):.0f} max={max(walls):.0f}")
print("oom_at_0.9:", [r["probe_id"] for r in rq
                      if r.get("inconclusive_class") == "out_of_memory"])
print("inconclusive:", [(r["probe_id"], r.get("inconclusive_class"))
                        for r in rq if r["evidence_grade"] == "INCONCLUSIVE"])

print("\n== fate of the 57 archived timeout INCONCLUSIVEs ==")
archived_ids = [json.loads(l)["probe_id"]
                for l in open(E1 / "equiv_observations_timeout_v2.jsonl",
                              encoding="utf-8") if l.strip()]
rq_by_id = {r["probe_id"]: r for r in rq}
fate = Counter()
for pid in archived_ids:
    r = rq_by_id.get(pid)
    fate[r["evidence_grade"] if r else "STILL_PENDING"] += 1
print(f"archived={len(archived_ids)} fate={dict(fate)}")
flipped = [pid for pid in archived_ids
           if rq_by_id.get(pid, {}).get("evidence_grade") == "WITNESSED_NON_EQUIVALENT"]
print(f"flipped to WITNESSED ({len(flipped)}):", flipped)
print("\nRECOVER_CHECK_DONE")
