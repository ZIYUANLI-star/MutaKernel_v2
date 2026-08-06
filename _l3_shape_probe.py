"""Real-forward shape probe for the two L3 tasks the meta device cannot resolve.

Scope: L3_P29 (SwinMLP) and L3_P30 (SwinTransformerV2), 2 tasks x 2 dtypes.
This is a *scheduling* measurement, not a calibration: it records the output
shape so the host-memory estimator can size those units.  It touches no
tolerance, no verdict, and no frozen artefact, which is why it is not subject to
the "calibrate only against frozen contracts" rule.

CPU-only (CUDA_VISIBLE_DEVICES cleared) and thread-capped so it cannot compete
with the methodology audit that currently owns the GPU.  Results are merged into
l3_scope/unit_size_table.json only; the live unit_size_table.json is read for
verification and never written.
"""
import io

import _remote

SCRIPT = r'''
import importlib.util, json, os, resource, time, traceback
from pathlib import Path

import torch

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
SCOPE = OUT / "l3_scope"
MK = "/root/mk_v2"
TARGETS = ("L3_P29", "L3_P30")
CMP_BYTES_PER_ELEM = 34.0
GB = float(1 << 30)

torch.set_num_threads(8)
print("=== L3 shape probe (real forward, CPU-only)  %s ==="
      % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
print("threads=%d  cuda_visible=%r" % (torch.get_num_threads(),
                                       os.environ.get("CUDA_VISIBLE_DEVICES")))

live_before = json.loads((OUT / "unit_size_table.json").read_text())
size = json.loads((SCOPE / "unit_size_table.json").read_text())
by_key = {r["task_key"]: r for r in size["subjects"]}

results = {}
for key in TARGETS:
    row = by_key.get(key)
    if row is None:
        print("\n%s: not in the scope size table" % key)
        continue
    path = os.path.join(MK, row["file"])
    print("\n---- %s (%s) ----" % (key, row["file"]))
    print("   previous error: %s" % row.get("error"))
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
    started = time.time()
    try:
        spec = importlib.util.spec_from_file_location("probe_%s" % key, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        init = module.get_init_inputs() if hasattr(module, "get_init_inputs") else []
        if not isinstance(init, (list, tuple)):
            init = [init]
        torch.manual_seed(42)
        model = module.Model(*list(init)).eval()
        inputs = module.get_inputs()
        if not isinstance(inputs, (list, tuple)):
            inputs = [inputs]
        in_numel = int(sum(t.numel() for t in inputs
                           if isinstance(t, torch.Tensor)))
        shapes = [list(t.shape) for t in inputs if isinstance(t, torch.Tensor)]
        with torch.no_grad():
            out = model(*inputs)
        wall = time.time() - started
        rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
        entry = {"task_key": key, "in_numel": in_numel, "in_shapes": shapes,
                 "probe_wall_s": round(wall, 1),
                 "probe_peak_rss_gb": round(rss1, 2),
                 "probe_method": "real forward, cpu, no_grad, seed 42"}
        if isinstance(out, torch.Tensor):
            entry["out_numel"] = int(out.numel())
            entry["out_shape"] = list(out.shape)
            entry["output_kind"] = "tensor"
        else:
            entry["out_numel"] = None
            entry["output_kind"] = type(out).__name__
            if isinstance(out, (tuple, list)):
                entry["out_shapes"] = [list(t.shape) for t in out
                                       if isinstance(t, torch.Tensor)]
            entry["error"] = ("non-tensor output (%s): outside the B9 port's "
                              "single-tensor domain" % type(out).__name__)
        print("   in_numel=%d in_shapes=%s" % (in_numel, shapes))
        print("   output_kind=%s out_numel=%s out_shape=%s"
              % (entry["output_kind"], entry.get("out_numel"),
                 entry.get("out_shape")))
        print("   wall=%.1fs  probe peak rss=%.2f GB (delta %.2f)"
              % (wall, rss1, rss1 - rss0))
        results[key] = entry
    except Exception as exc:
        wall = time.time() - started
        entry = {"task_key": key, "out_numel": None,
                 "probe_wall_s": round(wall, 1),
                 "probe_method": "real forward, cpu, no_grad, seed 42",
                 "error": "%s: %s" % (type(exc).__name__, str(exc)[:300]),
                 "traceback_tail": traceback.format_exc().splitlines()[-6:]}
        print("   REAL FORWARD FAILED after %.1fs: %s: %s"
              % (wall, type(exc).__name__, str(exc)[:220]))
        for line in entry["traceback_tail"]:
            print("      ", line[:170])
        results[key] = entry

print("\n=== merge into the scope size table (live table untouched) ===")
for key, entry in results.items():
    row = by_key[key]
    row.update({k: v for k, v in entry.items() if k != "task_key"})
    if row.get("out_numel") is not None:
        row.pop("error", None)
        for dtype, itemsize in (("float32", 4), ("float16", 2)):
            ref = 8.0 * (row["in_numel"] + row["out_numel"]) + itemsize * row["out_numel"]
            cmp_ = (CMP_BYTES_PER_ELEM + 2.0 * itemsize) * row["out_numel"]
            row["est_peak_gb_" + dtype] = round(max(ref, cmp_) / GB, 2)
        row["est_peak_gb"] = max(row["est_peak_gb_float32"],
                                 row["est_peak_gb_float16"])
        print("  %-8s est_peak f32=%.2f GB  f16=%.2f GB  reserve f32=%.2f GiB"
              % (key, row["est_peak_gb_float32"], row["est_peak_gb_float16"],
                 row["est_peak_gb_float32"] * 1.3))
    else:
        row["est_peak_gb"] = None
        print("  %-8s still unresolved: %s" % (key, row.get("error", "")[:110]))

size["shape_probe"] = {
    "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "targets": list(TARGETS),
    "purpose": ("scheduling-only static size profile; NOT a calibration and "
                "therefore not subject to the frozen-contract rule"),
    "results": results,
}
(SCOPE / "unit_size_table.json").write_text(json.dumps(size, indent=2),
                                            encoding="utf-8")
print("wrote %s" % (SCOPE / "unit_size_table.json"))

resolved = [r for r in size["subjects"] if r.get("out_numel") is not None]
print("\nscope size table: %d / %d subjects resolved"
      % (len(resolved), len(size["subjects"])))
units = sum(len(r["dtypes"]) for r in resolved)
print("units with a size estimate: %d / 500" % units)

live_after = json.loads((OUT / "unit_size_table.json").read_text())
print("\nlive unit_size_table.json unchanged: %s (subjects=%d)"
      % (live_after == live_before, len(live_after["subjects"])))
print("PROBE_DONE")
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_l3_shape_probe.py")
sftp.close()
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=8 "
               "MKL_NUM_THREADS=8 /root/miniconda3/bin/python -u "
               "/root/_l3_shape_probe.py 2>&1", timeout=2400)
c.close()
