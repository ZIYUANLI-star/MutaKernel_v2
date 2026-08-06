# -*- coding: utf-8 -*-
"""Probe 6: per-unit size table for all 200 subjects via the meta device
(shape propagation only, no allocation, no GPU), plus host-peak estimates and
an ETA model.  Writes /root/mk_v2_runs/e3_b9_calib/unit_size_table.json."""
import _remote as R

SNIPPET = r'''
import importlib.util, json, os, sys, traceback
import torch
sys.path.insert(0, "/root/mk_v2")
ROOT = "/root/mk_v2_runs/e3_b9_calib"
MK = "/root/mk_v2"

# measured on this box: bytes of host high-water per output element inside
# error_stats (see _b9fix_probe5: 34.0 B/elem, stable 1.7e7..2.0e8 elements)
CMP_BYTES_PER_ELEM = 34.0
GB = float(1 << 30)

table = json.load(open(os.path.join(ROOT, "task_table.json")))
rows = []
for task in table["tasks"]:
    path = os.path.join(MK, task["file"])
    row = {"task_key": task["task_key"], "file": task["file"],
           "dtypes": task["dtypes"], "reduction_heavy": task["reduction_heavy"]}
    try:
        spec = importlib.util.spec_from_file_location("meta_%s" % task["task_key"], path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with torch.device("meta"):
            init = module.get_init_inputs() if hasattr(module, "get_init_inputs") else []
            if not isinstance(init, (list, tuple)):
                init = [init]
            model = module.Model(*list(init)).eval()
            inputs = module.get_inputs()
            if not isinstance(inputs, (list, tuple)):
                inputs = [inputs]
            with torch.no_grad():
                out = model(*inputs)
        row["in_numel"] = int(sum(t.numel() for t in inputs
                                 if isinstance(t, torch.Tensor)))
        if isinstance(out, torch.Tensor):
            row["out_numel"] = int(out.numel())
            row["out_shape"] = list(out.shape)
        else:
            row["out_numel"] = None
            row["error"] = "non-tensor output"
    except Exception as exc:
        row["out_numel"] = None
        row["in_numel"] = None
        row["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:160])
    rows.append(row)

resolved = [r for r in rows if r["out_numel"] is not None]
failed = [r for r in rows if r["out_numel"] is None]
print("resolved %d / %d subjects on meta; failures %d" % (len(resolved), len(rows), len(failed)))
for r in failed:
    print("  FAILED", r["task_key"], r.get("error"))

for r in rows:
    if r["out_numel"] is None:
        r["est_peak_gb"] = None
        continue
    for dtype, itemsize in (("float32", 4), ("float16", 2)):
        ref_stage = 8.0 * (r["in_numel"] + r["out_numel"]) + itemsize * r["out_numel"]
        cmp_stage = (CMP_BYTES_PER_ELEM * r["out_numel"]
                     + 2.0 * itemsize * r["out_numel"])
        r["est_peak_gb_" + dtype] = round(max(ref_stage, cmp_stage) / GB, 2)
    r["est_peak_gb"] = max(r["est_peak_gb_float32"], r["est_peak_gb_float16"])

print()
print("=== biggest 25 subjects by estimated host peak ===")
for r in sorted(resolved, key=lambda x: -x["est_peak_gb"])[:25]:
    print("  %-8s out_numel=%-12d in_numel=%-12d peak_f32=%5.1fGB peak_f16=%5.1fGB %s"
          % (r["task_key"], r["out_numel"], r["in_numel"],
             r["est_peak_gb_float32"], r["est_peak_gb_float16"], r["out_shape"]))

print()
print("=== distribution of estimated peaks (per unit) ===")
import bisect
buckets = [(0, 2), (2, 5), (5, 12), (12, 25), (25, 50), (50, 100), (100, 1e9)]
units = []
for r in resolved:
    for dtype in r["dtypes"]:
        units.append((r["task_key"] + "__" + dtype, r["est_peak_gb_" + dtype],
                      r["out_numel"]))
for lo, hi in buckets:
    n = sum(1 for _, gb, _ in units if lo <= gb < hi)
    print("  [%5g, %5g) GB : %3d units" % (lo, hi, n))
print("  total units with a size estimate:", len(units))
print("  units above 2**24 output elements (new quantile path):",
      sum(1 for _, _, ne in units if ne > 2 ** 24))

out_path = os.path.join(ROOT, "unit_size_table.json")
json.dump({"created_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
           "cmp_bytes_per_elem_measured": CMP_BYTES_PER_ELEM,
           "note": ("est_peak_gb_<dtype> = max(fp64 reference stage, comparison "
                    "stage) host bytes; excludes the ~20GB critical-path worker"),
           "subjects": rows}, open(out_path, "w"), indent=2)
print("wrote", out_path)

print()
print("=== host cpu/mem facts ===")
print("nproc", os.cpu_count(), "torch.get_num_threads", torch.get_num_threads())
print("cpuset", open("/sys/fs/cgroup/cpuset/cpuset.cpus").read().strip())
print("mem limit GB", int(open("/sys/fs/cgroup/memory/memory.limit_in_bytes").read()) / GB)
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/_b9fix_sizes.py", "w") as fh:
    fh.write(SNIPPET)
sftp.close()
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u /root/_b9fix_sizes.py 2>&1",
      timeout=1800)
c.close()
print("PROBE6_DONE")
