#!/usr/bin/env python3
"""Minimal direct control: run ONLY the unmutated P53 kernel's forward on
mixed_extremes inputs (worker-identical seeds), timing each call.

No paired isolation/cloning -> fits in ~12GB (MK_GPU_MEMORY_FRACTION=0.18),
so a slow/hang signal is NOT confounded by OOM. Runs as a 300s-capped
subprocess wrapper below.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/root/mk_v2")
OUT = Path("/root/mk_v2_runs/e1")
CTRL = OUT / "_p53_control2"
CTRL.mkdir(exist_ok=True)

INNER = CTRL / "_inner.py"
INNER.write_text(r'''
import json, sys, time
from pathlib import Path
ROOT = Path("/root/mk_v2"); sys.path.insert(0, str(ROOT))
OUT = Path("/root/mk_v2_runs/e1")
import torch
torch.cuda.set_per_process_memory_fraction(0.18, 0)
from scripts.run_e1_probe_study import _load_probe_files, _resolve_problem_file
from src.bridge.eval_bridge import _load_module_from_path
from src.mutengine.mutant_runner import _load_module_from_source, _move_tree_to_device, clone_tree
from src.stress.policy_bank import STRESS_POLICIES

# original kernel source from the probe files (stable, not scratch-dir cfg)
kfs = _load_probe_files(OUT)
kf = next(k for k in kfs if k["kernel"]["problem_name"] == "L1_P53")
kernel_code = kf["kernel_source"]
kern = kf["kernel"]
problem_file = str(_resolve_problem_file(ROOT / "KernelBench", kern["level"], kern["problem_id"]))
device = "cuda"
base_seed = 50000; equiv_runs = 40  # worker constants -> stress seed = base+equiv+si

ref_mod = _load_module_from_path(problem_file, "ref_ctrl")
get_inputs = ref_mod.get_inputs
get_init_inputs = getattr(ref_mod, "get_init_inputs", lambda: [])

def seed_all(s):
    import random; random.seed(s)
    try:
        import numpy as np; np.random.seed(s % (2**32))
    except Exception: pass
    torch.manual_seed(s)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(s)

seed_all(base_seed)
init_args = get_init_inputs()
orig_mod = _load_module_from_source(kernel_code, "eqo_ctrl", str(CTRL) if False else "/tmp")
orig_cls = getattr(orig_mod, "ModelNew", None) or getattr(orig_mod, "Model")
model = (orig_cls(*clone_tree(init_args)) if isinstance(init_args,(list,tuple)) else orig_cls())
model = model.to(device).eval()
print("model built ok; init_args=", init_args, flush=True)

def run_forward(tag, args):
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        out = model(*args)
    torch.cuda.synchronize()
    dt = time.time() - t0
    ss = out.float().abs().sum().item() if hasattr(out, "float") else None
    print(f"[{tag}] forward_s={dt:.2f} out_shape={tuple(out.shape)} checksum={ss}", flush=True)
    del out
    torch.cuda.empty_cache()

# baseline normal input
seed_all(base_seed)
gen = get_inputs()
args = tuple(_move_tree_to_device(tuple(gen) if isinstance(gen,(list,tuple)) else (gen,), device))
print("baseline normal input ready", flush=True)
run_forward("NORMAL", args)
del args; torch.cuda.empty_cache()

policy_fn = STRESS_POLICIES["mixed_extremes"]
for si in range(3):
    seed = base_seed + equiv_runs + si
    seed_all(seed)
    template = get_inputs()
    stressed = policy_fn(clone_tree(template), seed)
    sv = list(stressed) if isinstance(stressed,(list,tuple)) else [stressed]
    t = sv[0]
    print(f"[mixed_extremes si={si}] input shape={tuple(t.shape)} dtype={t.dtype} "
          f"min={float(t.min()):.3e} max={float(t.max()):.3e} "
          f"has_nan={bool(t.isnan().any())} has_inf={bool(t.isinf().any())}", flush=True)
    args = tuple(_move_tree_to_device(tuple(sv), device))
    print(f"[mixed_extremes si={si}] launching forward (watch for hang)...", flush=True)
    run_forward(f"mixed_extremes_si{si}", args)
    del args, stressed, template; torch.cuda.empty_cache()

print("CONTROL_DONE_ALL_ROUNDS_COMPLETED", flush=True)
''')

env = dict(os.environ)
env["MK_GPU_MEMORY_FRACTION"] = "0.18"
env["PATH"] = "/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin"
env["TORCH_EXTENSIONS_DIR"] = "/root/mk_v2_runs/torch_ext"

print("launching minimal control (300s hard cap, frac=0.18)...", flush=True)
t0 = time.time()
try:
    p = subprocess.run(["/root/miniconda3/bin/python", "-u", str(INNER)],
                       cwd=str(ROOT), env=env, timeout=300,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("STDOUT:\n" + p.stdout.decode(errors="replace"))
    print("STDERR tail:\n" + p.stderr.decode(errors="replace")[-1500:])
    print("exit code:", p.returncode)
except subprocess.TimeoutExpired as e:
    print("!!! HARD TIMEOUT 300s -> original kernel HUNG on some round")
    if e.stdout: print("STDOUT so far:\n" + e.stdout.decode(errors="replace"))
    if e.stderr: print("STDERR so far:\n" + e.stderr.decode(errors="replace")[-1500:])
print(f"wall_s={time.time()-t0:.1f}")
