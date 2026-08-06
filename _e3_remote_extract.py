# -*- coding: utf-8 -*-
"""Remote: (1) explicit run of the three new test files, (2) C2/C3/C5
contract-draft extraction from the E2 frames, (3) B1u + B9 scheduler smoke on
a real KernelBench L1 task (CPU-only; candidate = the task's own reference).
Fetch the contract drafts back."""
import os
import _remote as R

c = R.connect()

print("### new test files, explicit")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest "
         "tests/test_e3_ports.py tests/test_b11_sanitizer.py tests/test_e2_inclusion.py "
         "-q 2>&1 | tail -5", timeout=900)

print("### contract drafts for C2/C3/C5 task keys (CPU-only, reference-only)")
code, out, err = R.run(
    c,
    "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
    "scripts/extract_contracts.py --kernelbench-root KernelBench "
    "--frames /root/mk_v2_runs/e2_reconcile/C2_collection_frame.jsonl "
    "/root/mk_v2_runs/e2_reconcile/C3_subject_frame.jsonl "
    "/root/mk_v2_runs/e2_reconcile/C5_collection_frame.jsonl "
    "--out /root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft.jsonl "
    "2>&1 | tail -15",
    timeout=1800,
)

print("### scheduler smoke on real KernelBench task (B1u then B9)")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
         "scripts/run_e3_external.py plan --baseline b1u --subject-id KB_L1_P1 "
         "--out /root/mk_v2_runs/e3_smoke/plan_b1u.json && "
         "CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
         "scripts/run_e3_external.py plan --baseline b9 --subject-id KB_L1_P1 "
         "--out /root/mk_v2_runs/e3_smoke/plan_b9.json", timeout=300)
task = "KernelBench/KernelBench/level1/1_Square_matrix_multiplication_.py"
for plan in ("plan_b1u.json", "plan_b9.json"):
    R.run(c, f"cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
             f"scripts/run_e3_external.py run --plan /root/mk_v2_runs/e3_smoke/{plan} "
             f"--task-module {task} --candidate-module {task} "
             f"--out-dir /root/mk_v2_runs/e3_smoke 2>&1 | tail -14", timeout=1800)

sftp = c.open_sftp()
local_dir = os.path.join("MutakernelV2", "实验", "补充实验数据", "contracts")
for name in ("contracts_c2c3c5_draft.jsonl", "contracts_c2c3c5_draft.freeze.json"):
    sftp.get(f"/root/mk_v2_runs/e2_reconcile/{name}", os.path.join(local_dir, name))
    print("fetched", name)
sftp.close()
c.close()
print("EXTRACT_DONE")
