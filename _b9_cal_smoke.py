# -*- coding: utf-8 -*-
"""GPU smoke before the full B9 calibration batch: L1_P1 fp32 + fp16, one
32-control plan each, --device cuda.  Outputs to a scratch _smoke dir."""
import _remote as R

PY = "/root/miniconda3/bin/python"
TASK = "KernelBench/KernelBench/level1/1_Square_matrix_multiplication_.py"
OUT = "/root/mk_v2_runs/e3_b9_calib/_smoke"

c = R.connect()
for dtype in ("float32", "float16"):
    print(f"### smoke {dtype}")
    R.run(c, f"cd /root/mk_v2 && {PY} scripts/run_e3_external.py plan "
             f"--baseline b9 --subject-id L1_P1 --b9-dtypes {dtype} "
             f"--out {OUT}/{dtype}/plan.json", timeout=120)
    R.run(c, f"cd /root/mk_v2 && {PY} scripts/run_e3_external.py run "
             f"--plan {OUT}/{dtype}/plan.json --task-module {TASK} "
             f"--candidate-module {TASK} --device cuda --allow-gpu "
             f"--out-dir {OUT}/{dtype} 2>&1 | tail -16", timeout=1800)
    R.run(c, f"head -2 {OUT}/{dtype}/b9_L1_P1_observations.jsonl", timeout=30)
c.close()
print("B9_SMOKE_DONE")
