# -*- coding: utf-8 -*-
"""Probe 2: failure tracebacks, subject shapes/numel, cgroup limits, guard."""
import _remote as R

SNIPPET = r'''
import json, glob, os, re, subprocess, sys
ROOT = "/root/mk_v2_runs/e3_b9_calib"
MK = "/root/mk_v2"

FAILED = ["L1_P7__float32","L1_P7__float16","L1_P11__float32","L1_P11__float16",
          "L1_P8__float32","L1_P8__float16","L1_P3__float32","L1_P3__float16",
          "L1_P9__float32","L1_P9__float16",
          "L1_P24__float32","L1_P24__float16","L1_P33__float32",
          "L1_P6__float16","L1_P16__float16","L1_P10__float16"]

print("=== run.log tails ===")
for u in FAILED:
    p = os.path.join(ROOT, "units", u, "run.log")
    print("---", u, "exists=%s" % os.path.exists(p))
    if os.path.exists(p):
        txt = open(p, encoding="utf-8", errors="replace").read()
        print("   size", len(txt))
        print("\n".join("   " + l for l in txt.strip().splitlines()[-18:]))

print()
print("=== unit dirs contents (sample) ===")
for u in ["L1_P3__float32", "L1_P24__float32", "L1_P6__float16"]:
    d = os.path.join(ROOT, "units", u)
    if os.path.isdir(d):
        print(u, sorted(os.listdir(d)))

print()
print("=== observations for controls_incomplete / heavy_tail ===")
for u in ["L1_P6__float16", "L1_P16__float16", "L1_P10__float16"]:
    key = u.split("__")[0]
    p = os.path.join(ROOT, "units", u, "b9_%s_observations.jsonl" % key)
    print("---", u, os.path.exists(p))
    if os.path.exists(p):
        rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        print("   n", len(rows))
        for r in rows[:3]:
            print("   ", json.dumps(r, sort_keys=True))
        errs = sorted({r["b9"]["max_abs_err"] for r in rows if r.get("b9")})
        print("   distinct max_abs_err:", errs)
        print("   statuses:", {r["status"] for r in rows})
        print("   reasons:", {r.get("reason") for r in rows})

print()
print("=== subject sources (shape constants + forward) ===")
KEYS = {"L1_P3":"3_Batched_matrix_multiplication.py",
        "L1_P6":"6_Matmul_with_large_K_dimension_.py",
        "L1_P7":"7_Matmul_with_small_K_dimension_.py",
        "L1_P8":"8_Matmul_with_irregular_shapes_.py",
        "L1_P9":"9_Tall_skinny_matrix_multiplication_.py",
        "L1_P11":"11_4D_tensor_matrix_multiplication.py",
        "L1_P24":"24_LogSoftmax.py",
        "L1_P33":"33_BatchNorm.py",
        "L1_P16":"16_Matmul_with_transposed_A.py",
        "L1_P10":"10_3D_tensor_matrix_multiplication.py",
        "L1_P1":"1_Square_matrix_multiplication_.py"}
for k, f in KEYS.items():
    p = os.path.join(MK, "KernelBench/KernelBench/level1", f)
    txt = open(p, encoding="utf-8").read()
    body = [l for l in txt.splitlines()
            if re.search(r"^(batch_size|M|N|K|dim|features|num_|scale)|torch\.(randn|rand)|return torch|def forward|def get_inputs", l)]
    print("---", k, f)
    for l in body:
        print("    ", l.strip())

print()
print("=== output numel (computed on CPU, float32, no_grad) ===")
sys.path.insert(0, MK)
import importlib.util, torch, gc, resource
def load(p, name):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
for k, f in KEYS.items():
    p = os.path.join(MK, "KernelBench/KernelBench/level1", f)
    try:
        m = load(p, "probe_%s" % k)
        torch.manual_seed(0)
        ins = m.get_inputs()
        init = m.get_init_inputs() if hasattr(m, "get_init_inputs") else []
        torch.manual_seed(42)
        model = m.Model(*(list(init) if isinstance(init, (list, tuple)) else [init])).eval()
        with torch.no_grad():
            out = model(*ins)
        print(k, "in_shapes", [tuple(t.shape) for t in ins if hasattr(t, "shape")],
              "out", tuple(out.shape), "numel", out.numel(),
              "OVER_LIMIT" if out.numel() > 16_000_000 else "")
        del out, model, ins
        gc.collect()
    except Exception as e:
        print(k, "ERR", type(e).__name__, e)
print("probe peak RSS GB", round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576, 2))

print()
print("=== cgroup ===")
print(open("/proc/self/cgroup").read().strip())
print(subprocess.run(["bash","-lc","ls /sys/fs/cgroup | head -40"],capture_output=True,text=True).stdout)
for f in ["/sys/fs/cgroup/memory/memory.limit_in_bytes",
          "/sys/fs/cgroup/memory/memory.usage_in_bytes",
          "/sys/fs/cgroup/memory/memory.max_usage_in_bytes",
          "/sys/fs/cgroup/memory/memory.failcnt",
          "/sys/fs/cgroup/memory/memory.stat"]:
    try:
        v = open(f).read().strip()
        if f.endswith("memory.stat"):
            v = " | ".join(l for l in v.splitlines() if l.split()[0] in
                           ("total_rss","total_cache","hierarchical_memory_limit","total_pgfault"))
        print(f, "=", v)
    except OSError as e:
        print(f, "ERR", e)

print()
print("=== guard_b9.sh ===")
print(open(os.path.join(ROOT, "guard_b9.sh"), encoding="utf-8").read())
print("=== guard log / lane logs ===")
print(open(os.path.join(ROOT, "guard_b9.log"), encoding="utf-8").read())
for L in range(4):
    print("--lane%d--" % L)
    print(open(os.path.join(ROOT, "lane%d.log" % L), encoding="utf-8").read())
print("=== run_manifest ===")
print(open(os.path.join(ROOT, "run_manifest.json"), encoding="utf-8").read())

print("=== dmesg oom (tail) ===")
print(subprocess.run(["bash","-lc","dmesg 2>/dev/null | grep -i -E 'oom|killed process' | tail -20 || echo NO_DMESG"],capture_output=True,text=True).stdout)
print("=== tests dir remote ===")
print(subprocess.run(["bash","-lc","ls %s/tests | head -50; %s/../miniconda3/bin/python -c 'import pytest; print(pytest.__version__)' 2>&1 | tail -1" % (MK, MK)],capture_output=True,text=True).stdout)
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/_b9fix_probe2.py", "w") as fh:
    fh.write(SNIPPET)
sftp.close()
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u /root/_b9fix_probe2.py 2>&1",
      timeout=900)
c.close()
print("PROBE2_DONE")
