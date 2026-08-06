"""One-off remote diagnosis: why does the corrected runner return UNKNOWN
on an original-kernel control?  Prints per-trial verdict reasons."""
from _remote import connect, run

DIAG = r'''
import sys, json
sys.path.insert(0, "/root/mk_v2")
import torch
from src.models import KernelInfo, Mutant, MutationSite
from src.mutengine.mutant_runner import MutantRunner
from src.bridge.eval_bridge import _load_module_from_path

details = json.load(open("/root/mk_v2/phase1_details/L1_P5.json"))
kern = details["kernel"]; m0 = details["mutants"][0]
code = m0["original_code"]

kernel = KernelInfo(problem_id=int(kern["problem_id"]), level=int(kern["level"]),
                    problem_name=kern["problem_name"], source_path="", kernel_code=code,
                    reference_module_path="", language=kern.get("language","cuda"))
site = MutationSite(line_start=1, line_end=1)
mut = Mutant(id="DIAG_L1_P5_ORIG", operator_name="none", operator_category="A",
             site=site, original_code=code, mutated_code=code, description="")

import glob
pf = sorted(glob.glob("/root/mk_v2/KernelBench/KernelBench/level1/5_*.py"))[0]
ref_mod = _load_module_from_path(pf, "diag_ref")
runner = MutantRunner(atol=1e-2, rtol=1e-2, num_test_inputs=5, device="cuda", seed=42)
runner.run_mutant(kernel, mut, ref_mod, ref_mod.get_inputs,
                  getattr(ref_mod, "get_init_inputs", lambda: []))
print("STATUS:", mut.status.value)
print("ERROR:", (mut.error_message or "")[:200])
for t in mut.equiv_detail.get("phase1_validation", {}).get("trials", []):
    reason = str(t.get("reason", ""))[:220]
    print(f"  trial={t.get('trial')} status={t.get('status')} reason={reason}")
    for err in (t.get("errors") or [])[:3]:
        print("    err:", str(err)[:220])
'''

c = connect()
run(c, "cat > /root/mk_v2/_diag_e0.py << 'PYEOF'\n" + DIAG + "\nPYEOF")
run(c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
       "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
       "/root/miniconda3/bin/python _diag_e0.py 2>&1 | tail -25", timeout=900)
c.close()
print("DIAG_DONE")
