#!/usr/bin/env python3
"""Control: run the UNMUTATED P53 kernel against itself on mixed_extremes.

Determines root cause of the lane3 hang:
  * original kernel ALSO hangs on mixed_extremes  -> policy input escapes the
    kernel's contract domain (legitimate rejection, not a mutant witness)
  * only the mutant hangs                          -> hang is a non-termination
    non-equivalence signal attributable to the mutation

Isolated subprocess, MK_GPU_MEMORY_FRACTION<=0.15, 300s hard timeout. Does NOT
touch the running lane3/lane4 drivers.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/root/mk_v2")
OUT = Path("/root/mk_v2_runs/e1")
sys.path.insert(0, str(ROOT))

# Source cfg = the currently running P53 probe (has original kernel_code + problem_file)
SRC_CFG = OUT / "e1cse_71e__lrp" / "cfg_L1_P53__const_perturb__0.json"
src = json.loads(SRC_CFG.read_text())

control_dir = OUT / "_p53_control"
control_dir.mkdir(exist_ok=True)

cfg = dict(src)
cfg["mutant_id"] = "L1_P53__ORIGINAL_CONTROL__mixed_extremes"
cfg["operator_name"] = ""
# original-vs-original: candidate is the unmutated kernel source
cfg["mutated_code"] = src["kernel_code"]
cfg["stress_policies"] = ["mixed_extremes"]
cfg["stress_repeats"] = 3
cfg["equiv_runs"] = 3          # a few random rounds to confirm the kernel runs at all
cfg["round_timeout"] = 90      # same production watchdog

cfg_path = control_dir / "cfg_control.json"
res_path = control_dir / "res_control.json"
cfg_path.write_text(json.dumps(cfg))

env = dict(os.environ)
env["MK_GPU_MEMORY_FRACTION"] = "0.15"
env["PATH"] = "/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin"
env["TORCH_EXTENSIONS_DIR"] = "/root/mk_v2_runs/torch_ext"

print("problem_file:", cfg["problem_file"])
print("kernel_code len:", len(cfg["kernel_code"]), "identical control:", cfg["mutated_code"] == cfg["kernel_code"])
print("launching control worker (300s hard cap, frac=0.15, mixed_extremes x3, +3 random)...", flush=True)

t0 = time.time()
timed_out = False
try:
    p = subprocess.run(
        ["/root/miniconda3/bin/python", "scripts/_mutant_worker.py",
         str(cfg_path), str(res_path)],
        cwd=str(ROOT), env=env, timeout=300,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    print("worker exit code:", p.returncode)
    if p.stderr:
        print("STDERR tail:", p.stderr.decode(errors="replace")[-800:])
except subprocess.TimeoutExpired:
    timed_out = True
    print("!!! CONTROL HARD TIMEOUT at 300s -> worker was killed")

wall = time.time() - t0
print(f"wall_s={wall:.1f} hard_timed_out={timed_out}")

if res_path.exists():
    res = json.loads(res_path.read_text())
    trials = res.get("trials") or []
    print("validation_status:", res.get("validation_status"))
    print("valid_rounds:", res.get("valid_rounds"), "round_timeouts:", res.get("round_timeouts"), "partial:", res.get("partial"))
    print("--- per-round ---")
    for t in trials:
        print("  ", t.get("round_type"), t.get("policy"), "sub", t.get("sub_index"),
              "->", t.get("status"), "| round_timeout=", t.get("round_timeout"),
              "|", (t.get("reason") or "")[:80])
else:
    print("no result file written (worker killed before any snapshot)")
