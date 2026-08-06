"""One-off detail dump of the interim offline-analysis outputs."""
import json
from collections import Counter
from pathlib import Path

O = Path("MutakernelV2/实验/重跑实验数据/离线分析/outputs")

a1 = json.loads((O / "a1_crossfit_closure.json").read_text(encoding="utf-8"))
print("== A1 ==")
print("per_fold:", a1["per_fold"])
print("lower k=1..12:", [(p["k"], p["closure_rate"]) for p in a1["closure_curve_lower"][:12]])
print("upper k=1..12:", [(p["k"], p["closure_rate"]) for p in a1["closure_curve_upper"][:12]])
unclosed = [r for r in a1["per_probe"] if not r["closed_at_planned_k"]]
print("unclosed:", Counter(r["classification"] for r in unclosed))
for r in unclosed:
    ne = sum(1 for s in r["planned_case_status"] if s["recorded"] == "not_executed")
    print(f"  {r['classification'][:30]:30} {r['probe_id']:40} {r['fault_class']:10} "
          f"wit={r['witness_policy_label']:22} cf_rank={r['crossfit_rank_of_witness']} not_exec={ne}")

a2 = json.loads((O / "a2_sole_detector.json").read_text(encoding="utf-8"))
print("\n== A2 ==")
print("proxy:", json.dumps(a2["proxy"], indent=1))
print("witness policy breakdown:",
      Counter(r["witness_policy"] for r in a2["per_defect"]).most_common())

a3 = json.loads((O / "a3_budget_recall.json").read_text(encoding="utf-8"))
print("\n== A3 ==")
combined = a3["recall_curve_combined"]
for target in (0.5, 0.8, 0.9, 0.95, 1.0):
    pt = next((p for p in combined if p["recall"] is not None and p["recall"] >= target), None)
    if pt:
        print(f"  recall >= {target}: budget {pt['budget_rounds']} rounds ({pt['witnesses']} wit)")
print("  phase-local final:", a3["recall_curve_phase_local"][-1])
print("  combined final:", combined[-1])
print("  a13 groups:", json.dumps(a3["a13_group_comparison"], indent=1))
top = sorted(a3["policy_yield_equiv"], key=lambda s: -s["hit_rate_per_round"])[:8]
for s in top:
    print(f"  equiv {s['policy']:24} rounds={s['rounds']:6} wit={s['witnesses']:3} "
          f"hit={s['hit_rate_per_round']:.4f} share_rounds={s['budget_share_rounds']:.4f} "
          f"share_ms={s['budget_share_wall_ms']}")

a4 = json.loads((O / "a4_cost_c1.json").read_text(encoding="utf-8"))
print("\n== A4 ==")
for name, s in a4["sections"].items():
    print(f"  {name:26} n={s.get('n'):5} med={s.get('median_ms')} p95={s.get('p95_ms')} "
          f"total_h={s.get('total_gpu_hours')}")
print("  phase_gpu_busy:", json.dumps(a4["phase_gpu_busy"], indent=1))
print("  per_1000:", a4["per_1000_candidates_gpu_hours"])
