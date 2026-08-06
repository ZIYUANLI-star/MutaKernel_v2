# -*- coding: utf-8 -*-
"""Close the B9 calibration loop on the KB_L1_P1 smoke: calibrate the
per-(subject,dtype) tolerance from the control run's max-abs errors
(p95 x 1.5), inject it into the plan, rerun -> expect PASS."""
import _remote as R

REMOTE_SNIPPET = r'''
import json, sys
sys.path.insert(0, "/root/mk_v2")
from src.experiments.external_ports import calibrate_tolerance

obs_path = "/root/mk_v2_runs/e3_smoke/b9_KB_L1_P1_observations.jsonl"
errors = []
for line in open(obs_path, encoding="utf-8"):
    row = json.loads(line)
    errors.append(row["b9"]["max_abs_err"])
tol = calibrate_tolerance(errors)
print("control max_abs errors: min=%.3g max=%.3g" % (min(errors), max(errors)))
print("calibrated tol (p95 x 1.5): %.6g" % tol)

plan_path = "/root/mk_v2_runs/e3_smoke/plan_b9.json"
plan = json.loads(open(plan_path, encoding="utf-8").read())
for case in plan["cases"]:
    case["parameters"]["calibrated_tol"] = tol
out = "/root/mk_v2_runs/e3_smoke/plan_b9_calibrated.json"
open(out, "w", encoding="utf-8").write(json.dumps(plan, indent=2))
print("wrote", out)
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_b9_cal.py", "w") as fh:
    fh.write(REMOTE_SNIPPET)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _b9_cal.py", timeout=120)
task = "KernelBench/KernelBench/level1/1_Square_matrix_multiplication_.py"
R.run(c, f"cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
         f"scripts/run_e3_external.py run --plan /root/mk_v2_runs/e3_smoke/plan_b9_calibrated.json "
         f"--task-module {task} --candidate-module {task} "
         f"--out-dir /root/mk_v2_runs/e3_smoke_cal 2>&1 | tail -14", timeout=1800)
R.run(c, "rm /root/mk_v2/_b9_cal.py", timeout=30)
c.close()
print("CALIBRATE_DONE")
