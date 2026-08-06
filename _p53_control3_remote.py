#!/usr/bin/env python3
"""Clean original-vs-mutant control on mixed_extremes, one forward per fresh
subprocess (no cross-round memory accumulation).

For model in {orig, mut(const_perturb__0)} x si in {0,1,2}: build model, make the
worker-identical mixed_extremes input, time a single forward under a 150s cap.
  * completes fast for both      -> hang is environmental (mem/contention), not kernel
  * orig fast, mut hangs/timeout -> mutant non-termination (non-equivalence signal)
  * both hang                    -> policy escapes contract domain (legit rejection)
"""
import json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path("/root/mk_v2"); OUT = Path("/root/mk_v2_runs/e1")
CTRL = OUT / "_p53_control3"; CTRL.mkdir(exist_ok=True)
INNER = CTRL / "_inner_one.py"
INNER.write_text(r'''
import json, sys, time
from pathlib import Path
ROOT = Path("/root/mk_v2"); sys.path.insert(0, str(ROOT))
OUT = Path("/root/mk_v2_runs/e1")
which = sys.argv[1]; si = int(sys.argv[2])
import torch
torch.cuda.set_per_process_memory_fraction(0.18, 0)
from scripts.run_e1_probe_study import _load_probe_files, _resolve_problem_file
from src.bridge.eval_bridge import _load_module_from_path
from src.mutengine.mutant_runner import _load_module_from_source, _move_tree_to_device, clone_tree
from src.stress.policy_bank import STRESS_POLICIES

kfs = _load_probe_files(OUT)
kf = next(k for k in kfs if k["kernel"]["problem_name"] == "L1_P53")
kern = kf["kernel"]
problem_file = str(_resolve_problem_file(ROOT / "KernelBench", kern["level"], kern["problem_id"]))
if which == "orig":
    code = kf["kernel_source"]
else:
    probe = next(p for p in kf["probes"] if p["probe_id"] == "L1_P53__const_perturb__0")
    code = probe["mutated_code"]

def seed_all(s):
    import random; random.seed(s)
    try:
        import numpy as np; np.random.seed(s % (2**32))
    except Exception: pass
    torch.manual_seed(s)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(s)

base_seed=50000; equiv_runs=40
ref_mod = _load_module_from_path(problem_file, "ref_ctrl3")
get_inputs = ref_mod.get_inputs
get_init_inputs = getattr(ref_mod, "get_init_inputs", lambda: [])
seed_all(base_seed); init_args = get_init_inputs()
mod = _load_module_from_source(code, "eqx_ctrl3", "/tmp")
cls = getattr(mod, "ModelNew", None) or getattr(mod, "Model")
model = (cls(*clone_tree(init_args)) if isinstance(init_args,(list,tuple)) else cls()).to("cuda").eval()

seed = base_seed + equiv_runs + si
seed_all(seed)
template = get_inputs()
stressed = STRESS_POLICIES["mixed_extremes"](clone_tree(template), seed)
del template
sv = list(stressed) if isinstance(stressed,(list,tuple)) else [stressed]
args = tuple(_move_tree_to_device(tuple(sv), "cuda"))
del stressed, sv
print(f"{which} si={si} input ready; launching forward", flush=True)
torch.cuda.synchronize(); t0=time.time()
with torch.no_grad():
    out = model(*args)
torch.cuda.synchronize(); dt=time.time()-t0
cs = out.float().abs().sum().item()
print(f"RESULT {which} si={si} forward_s={dt:.3f} out_shape={tuple(out.shape)} checksum={cs}", flush=True)
''')

env = dict(os.environ)
env["MK_GPU_MEMORY_FRACTION"] = "0.18"
env["PATH"] = "/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin"
env["TORCH_EXTENSIONS_DIR"] = "/root/mk_v2_runs/torch_ext"
CAP = 150

for which in ("orig", "mut"):
    for si in (0, 1, 2):
        print(f"\n===== {which} si={si} (cap {CAP}s) =====", flush=True)
        t0 = time.time()
        try:
            p = subprocess.run(["/root/miniconda3/bin/python", "-u", str(INNER), which, str(si)],
                               cwd=str(ROOT), env=env, timeout=CAP,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(p.stdout.decode(errors="replace").rstrip())
            errt = p.stderr.decode(errors="replace").rstrip()
            if errt: print("STDERR:", errt[-600:])
            print(f"exit={p.returncode} wall_s={time.time()-t0:.1f}")
        except subprocess.TimeoutExpired as e:
            print(f"!!! {which} si={si} HUNG: exceeded {CAP}s cap (forward did not return)")
            if e.stdout: print(e.stdout.decode(errors='replace').rstrip())
            print(f"wall_s={time.time()-t0:.1f}")
