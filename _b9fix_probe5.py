# -*- coding: utf-8 -*-
"""Probe 5: (a) defect-3 evidence, (b) memory of the DEPLOYED error_stats,
(c) end-to-end rerun of a real over-limit subject through the real harness,
CPU-only and thread-capped so the critical-path CSE worker is not disturbed."""
import _remote as R

D3 = r'''
import json, os
ROOT = "/root/mk_v2_runs/e3_b9_calib"
for u in ["L1_P6__float16", "L1_P6__float32", "L1_P16__float16", "L1_P10__float16"]:
    key = u.split("__")[0]
    p = os.path.join(ROOT, "units", u, "b9_%s_observations.jsonl" % key)
    print("=== %s (%s) ===" % (u, "present" if os.path.exists(p) else "MISSING"))
    if not os.path.exists(p):
        continue
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    print("  n=%d statuses=%s" % (len(rows), sorted({r["status"] for r in rows})))
    print("  reasons=%s" % sorted({str(r.get("reason")) for r in rows}))
    print("  tol=%s" % sorted({r.get("calibrated_tol") for r in rows}))
    kinds = {}
    errs = {}
    for r in rows:
        b9 = r.get("b9") or {}
        kinds[b9.get("failure_kind")] = kinds.get(b9.get("failure_kind"), 0) + 1
        e = b9.get("max_abs_err")
        errs[e] = errs.get(e, 0) + 1
    print("  failure_kinds=%s" % kinds)
    print("  max_abs_err histogram=%s" % sorted(errs.items(), key=lambda kv: str(kv[0])))
    print("  first row: %s" % json.dumps(rows[0], sort_keys=True))
'''

MEM = r'''
import resource, sys, time
import torch
sys.path.insert(0, "/root/mk_v2")
from src.experiments.external_ports.b9_seeded_fuzzing import error_stats
torch.set_num_threads(8)
N = int(sys.argv[1])
torch.manual_seed(1)
ref = torch.rand(N, dtype=torch.float32) * 20.0 - 10.0
out = ref + torch.rand(N, dtype=torch.float32) * 1e-4
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
t0 = time.time()
s = error_stats(out, ref, 1e-5)
dt = time.time() - t0
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
print("DEPLOYED N=%d base=%.2fGB peak=%.2fGB delta=%.2fGB bytes/elem=%.1f wall=%.1fs"
      % (N, base, peak, peak - base, (peak - base) * 1073741824.0 / N, dt))
print("   p50=%.6g p90=%.6g p99=%.6g count=%d" % (s["p50_abs"], s["p90_abs"], s["p99_abs"], s["count"]))
'''

E2E = r'''
import json, subprocess, os, resource
MK = "/root/mk_v2"
PY = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_b9_calib/_quantile_fix_check"
os.makedirs(OUT, exist_ok=True)
task = "KernelBench/KernelBench/level1/8_Matmul_with_irregular_shapes_.py"
plan_path = OUT + "/plan_L1_P8_f32.json"
r = subprocess.run([PY, "scripts/run_e3_external.py", "plan", "--baseline", "b9",
                    "--subject-id", "L1_P8", "--b9-dtypes", "float32",
                    "--out", plan_path], cwd=MK, capture_output=True, text=True)
print(r.stdout.strip(), r.stderr.strip()[:400])
plan = json.load(open(plan_path))
plan["cases"] = plan["cases"][:2]            # 2 of 32 cases: proof, not a run
json.dump(plan, open(plan_path, "w"), indent=2)
env = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "8",
       "MKL_NUM_THREADS": "8"}
r = subprocess.run([PY, "scripts/run_e3_external.py", "run", "--plan", plan_path,
                    "--task-module", task, "--candidate-module", task,
                    "--device", "cpu", "--out-dir", OUT],
                   cwd=MK, capture_output=True, text=True, env=env)
print("exit", r.returncode)
print(r.stdout.strip()[-1500:])
if r.returncode != 0:
    print("STDERR", r.stderr.strip()[-2500:])
obs = OUT + "/b9_L1_P8_observations.jsonl"
if os.path.exists(obs):
    for line in open(obs):
        print("OBS", line.strip())
print("peak RSS GB", round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1048576, 2))
'''

c = R.connect()
sftp = c.open_sftp()
for name, body in [("_b9fix_d3.py", D3), ("_b9fix_mem2.py", MEM), ("_b9fix_e2e.py", E2E)]:
    with sftp.open("/root/" + name, "w") as fh:
        fh.write(body)
sftp.close()

print("### A. defect-3 evidence")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u /root/_b9fix_d3.py 2>&1",
      timeout=300)
print("### B. deployed error_stats memory")
for n in [16_777_216, 100_000_000, 200_000_000]:
    R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 "
             "/root/miniconda3/bin/python -u /root/_b9fix_mem2.py %d 2>&1" % n, timeout=900)
print("### C. end-to-end on a real over-limit subject (L1_P8, 48.6M elems, CPU)")
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u /root/_b9fix_e2e.py 2>&1", timeout=1800)
print("### D. critical path untouched?")
R.run(c, "ps -eo pid,rss,etimes,args | grep '_mutant_[w]orker' | awk '{print $1,$2,$3}'; "
         "cat /sys/fs/cgroup/memory/memory.usage_in_bytes /sys/fs/cgroup/memory/memory.failcnt; "
         "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader", timeout=120)
c.close()
print("PROBE5_DONE")
