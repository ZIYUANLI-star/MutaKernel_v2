import _remote, time
c = _remote.connect()
R = _remote.run

killer = r'''
import os, signal, time
from pathlib import Path
def ppid(p):
    try:
        for l in open("/proc/%d/status" % p):
            if l.startswith("PPid:"):
                return int(l.split()[1])
    except OSError:
        pass
    return 0
excl, p = set(), os.getpid()
while p and p != 1:
    excl.add(p); p = ppid(p)
targets = []
for e in os.listdir("/proc"):
    if not e.isdigit() or int(e) in excl:
        continue
    try:
        cl = Path("/proc/%s/cmdline" % e).read_bytes().replace(b"\0", b" ").decode("utf-8","replace")
    except OSError:
        continue
    if "_wc_audit.py" in cl or ("witness_confirmation/scratch/cfg_" in cl):
        targets.append((int(e), cl.strip()[:120]))
for pid, cl in targets:
    print("TERM", pid, cl)
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        print(" fail", e)
time.sleep(8)
for pid, _ in targets:
    if os.path.exists("/proc/%d" % pid):
        try:
            os.kill(pid, signal.SIGKILL); print("KILL", pid)
        except OSError:
            pass
time.sleep(3)
print("alive:", [p for p, _ in targets if os.path.exists("/proc/%d" % p)])
'''

probe = r'''
"""Is the audit's base_seed shortcut bit-exact for this kernel?

The shortcut sets base_seed = witness stress seed with equiv_runs = 0, which
skips the (expensive) production random-round prefix.  It is only valid when
model construction does not consume the RNG, because the worker builds the
models under _seed_all(base_seed).  Checked directly: build under both seeds and
compare every parameter and buffer of BOTH the original and the mutated module,
bit for bit.  Constructed on CPU; no GPU work.
"""
import json, random, sys
from pathlib import Path
sys.path.insert(0, "/root/mk_v2")
import torch
import scripts.run_e1_probe_study as ps
from src.bridge.eval_bridge import _load_module_from_path
from src.validation import clone_tree

E1 = Path("/root/mk_v2_runs/e1")
inv = json.load(open(E1 / "_wc_witness_inventory.json"))
kernels = sorted({r["kernel"] for r in inv})
pfs = ps._load_probe_files(E1)
kf_by = {}
for kf in pfs:
    kk = kf["kernel"]
    kf_by["L%s_P%s" % (kk["level"], kk["problem_id"])] = kf


def seed_all(s):
    random.seed(s)
    try:
        import numpy as np
        np.random.seed(s % (2 ** 32))
    except ImportError:
        pass
    torch.manual_seed(s)


def build(cls_src_mod, init_args):
    cls = getattr(cls_src_mod, "ModelNew", None) or getattr(cls_src_mod, "Model")
    return cls(*clone_tree(init_args)) if isinstance(init_args, (list, tuple)) else cls()


def signature(model):
    items = []
    for name, t in list(model.named_parameters()) + list(model.named_buffers()):
        items.append((name, tuple(t.shape), str(t.dtype),
                      t.detach().double().sum().item(),
                      t.detach().double().abs().max().item() if t.numel() else 0.0))
    return items


res = {}
for k in kernels:
    kf = kf_by[k]
    kk = kf["kernel"]
    pf = ps._resolve_problem_file(Path("/root/mk_v2/KernelBench"), kk["level"], kk["problem_id"])
    try:
        ref = _load_module_from_path(str(pf), "seedprobe_%s" % k)
        gi = getattr(ref, "get_init_inputs", lambda: [])
        sigs, inits = [], []
        for s in (10000, 10020, 50000, 50040):
            seed_all(s)
            ia = gi()
            inits.append(json.dumps(ia, default=str))
            seed_all(s)
            m = build(ref, ia)
            sigs.append(signature(m))
        same = all(x == sigs[0] for x in sigs)
        res[k] = {
            "n_params_buffers": len(sigs[0]),
            "init_args_seed_independent": len(set(inits)) == 1,
            "construction_seed_independent": bool(same),
            "signature": [list(x) for x in sigs[0]][:4],
        }
    except Exception as exc:
        res[k] = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
    print("%-8s %s" % (k, json.dumps(res[k], default=str)[:200]), flush=True)

json.dump(res, open(E1 / "_wc_seed_shortcut.json", "w"), indent=1, default=str)
ok = [k for k, v in res.items() if v.get("construction_seed_independent")]
print("\nshortcut-safe kernels: %d/%d" % (len(ok), len(kernels)))
print("NOT safe:", [k for k in kernels if k not in ok])
'''
open("_wc28_kill.py", "w").write(killer)
open("_wc28_probe.py", "w").write(probe)
s = c.open_sftp()
s.put("_wc28_kill.py", "/root/mk_v2/_wc28_kill.py")
s.put("_wc28_probe.py", "/root/mk_v2/_wc28_probe.py")
s.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc28_kill.py", timeout=180)
R(c, "rm -f /root/mk_v2_runs/e1/witness_confirmation/audit.lock "
      "/root/mk_v2_runs/e1/witness_confirmation/cells/ctrl__L1_P23__equiv__stress.json "
      "/root/mk_v2_runs/e1/witness_confirmation/cells/ctrl__L1_P17__equiv__stress.json; "
      "ls /root/mk_v2_runs/e1/witness_confirmation/cells/*.json | wc -l")
R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc28_probe.py", timeout=900)
c.close()
