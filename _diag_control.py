"""Remote diagnostic: why does the corrected runner return INCONCLUSIVE on
un-mutated original controls that the legacy runner passes as 'survived'?

Runs MutantRunner.run_mutant on a handful of original controls (mutated_code =
original_code) and dumps the per-trial verdict status + reason captured in
mutant.equiv_detail. Read-only diagnostic; writes nothing to the run dirs.
"""
import json
import sys
from pathlib import Path

ROOT = Path("/root/mk_v2")
sys.path.insert(0, str(ROOT))

from scripts.run_e0_flip_rerun import load_probes, resolve_problem_file  # noqa: E402
from src.models import KernelInfo, Mutant, MutationSite  # noqa: E402
from src.mutengine.mutant_runner import MutantRunner  # noqa: E402
from src.bridge.eval_bridge import _load_module_from_path  # noqa: E402

TARGETS = sys.argv[1:] or ["L1_P19", "L1_P37", "L1_P25", "L1_P21", "L2_P84"]

probes = load_probes(ROOT / "phase1_details")
by_problem = {}
for p in probes:
    by_problem.setdefault(p["problem_name"], p)

for name in TARGETS:
    p = by_problem.get(name)
    if p is None:
        print(f"=== {name}: no probe found ===")
        continue
    problem_file = resolve_problem_file(ROOT / "KernelBench", p["level"], p["problem_id"])
    kernel = KernelInfo(
        problem_id=p["problem_id"], level=p["level"],
        problem_name=name, source_path="", kernel_code=p["original_code"],
        reference_module_path=str(problem_file), language=p["language"],
    )
    site = MutationSite(line_start=1, line_end=1, col_start=0, col_end=0,
                        original_code="", node_type="")
    mutant = Mutant(
        id=f"{name}__ORIGINAL_CONTROL", operator_name="none",
        operator_category="A", site=site,
        original_code=p["original_code"], mutated_code=p["original_code"],
        description="diagnostic control",
    )
    runner = MutantRunner(atol=1e-2, rtol=1e-2, num_test_inputs=5,
                          device="cuda", seed=42)
    safe = name.replace("-", "_")
    ref_mod = _load_module_from_path(str(problem_file), f"ref_diag_{safe}")
    get_inputs = ref_mod.get_inputs
    get_init = getattr(ref_mod, "get_init_inputs", lambda: [])
    runner.run_mutant(kernel, mutant, ref_mod, get_inputs, get_init)

    print(f"\n=== {name}  ->  status={mutant.status.value}  "
          f"err={(mutant.error_message or '')[:160]}")
    detail = (mutant.equiv_detail or {}).get("phase1_validation", {})
    for t in detail.get("trials", []):
        line = {k: t.get(k) for k in ("trial", "seed", "phase", "status", "reason")}
        print("   ", json.dumps(line, ensure_ascii=False)[:400])
        for e in (t.get("errors") or [])[:2]:
            print("        err:", json.dumps(e, ensure_ascii=False)[:300])

print("\nDIAG_DONE")
