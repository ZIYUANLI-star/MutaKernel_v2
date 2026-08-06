"""A4: build the 250-task / 500-unit B9 tables from the re-extracted draft.

Deliberately writes into a separate scope directory instead of replacing the
live task_table.json / unit_size_table.json.  Reason: _b9_resume_prep.build()
reads those two files, and my stage-1 chainer calls it to decide which units
stage 1 contains.  Replacing them while the first wave is in flight would
silently grow stage 1 from the 336 units that were approved to 336 + the new L3
units -- a scope change nobody asked for.  The live files therefore stay as they
are until the stage-1/stage-2 schedule for the L3 units is decided.

Everything here is CPU-only: the task table is pure JSON bookkeeping, and the
size table uses torch's meta device (shape propagation, no allocation, no GPU),
so it cannot contend with B9 or with the witness-confirmation audit.
"""
import io

import _remote

SCRIPT = r'''
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, "/root/mk_v2")

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
SCOPE = OUT / "l3_scope"
SCOPE.mkdir(parents=True, exist_ok=True)
NEW_DRAFT = Path("/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft_l3.jsonl")

print("=== A4 table rebuild (scope dir, live files untouched)  %s ==="
      % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
live_task = json.loads((OUT / "task_table.json").read_text())
live_size = json.loads((OUT / "unit_size_table.json").read_text())
print("live task_table.json : n_tasks=%d n_units=%d gaps=%d"
      % (live_task["n_tasks"], live_task["n_units"], len(live_task["gaps"])))
print("live unit_size_table : subjects=%d" % len(live_size["subjects"]))

import _b9_calib_prep as prep
prep.DRAFT = NEW_DRAFT
prep.OUT = SCOPE
prep.main()

table = json.loads((SCOPE / "task_table.json").read_text())
print("\nnew task_table: n_tasks=%d n_units=%d reduction_heavy=%d gaps=%d"
      % (table["n_tasks"], table["n_units"], table["n_reduction_heavy"],
         len(table["gaps"])))
lv = {}
for t in table["tasks"]:
    lv["L%d" % t["level"]] = lv.get("L%d" % t["level"], 0) + 1
print("by level:", dict(sorted(lv.items())))
print("source_sha256:", table["source_sha256"])

# ---- size table via the meta device (no allocation, no GPU) ----
import importlib.util
import torch

CMP_BYTES_PER_ELEM = 34.0
GB = float(1 << 30)
rows = []
for task in table["tasks"]:
    path = os.path.join("/root/mk_v2", task["file"])
    row = {"task_key": task["task_key"], "file": task["file"],
           "level": task["level"], "dtypes": task["dtypes"],
           "reduction_heavy": task["reduction_heavy"]}
    try:
        spec = importlib.util.spec_from_file_location(
            "meta_%s" % task["task_key"], path)
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
            row["error"] = "non-tensor output (%s)" % type(out).__name__
    except Exception as exc:
        row["out_numel"] = None
        row["in_numel"] = row.get("in_numel")
        row["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:160])
    rows.append(row)

for r in rows:
    if r["out_numel"] is None:
        r["est_peak_gb"] = None
        continue
    for dtype, itemsize in (("float32", 4), ("float16", 2)):
        ref_stage = 8.0 * (r["in_numel"] + r["out_numel"]) + itemsize * r["out_numel"]
        cmp_stage = (CMP_BYTES_PER_ELEM + 2.0 * itemsize) * r["out_numel"]
        r["est_peak_gb_" + dtype] = round(max(ref_stage, cmp_stage) / GB, 2)
    r["est_peak_gb"] = max(r["est_peak_gb_float32"], r["est_peak_gb_float16"])

resolved = [r for r in rows if r["out_numel"] is not None]
failed = [r for r in rows if r["out_numel"] is None]
l3 = [r for r in rows if r["level"] == 3]
l3_ok = [r for r in l3 if r["out_numel"] is not None]
l3_bad = [r for r in l3 if r["out_numel"] is None]
print("\n=== meta-device shape resolution ===")
print("resolved %d / %d subjects; unresolved %d" % (len(resolved), len(rows),
                                                    len(failed)))
print("L3 alone: resolved %d / %d ; unresolved %d"
      % (len(l3_ok), len(l3), len(l3_bad)))

print("\n=== L3 unresolved, classified ===")
kinds = {}
for r in l3_bad:
    err = r.get("error", "?")
    key = ("non-tensor output (outside the B9 port's single-tensor domain)"
           if err.startswith("non-tensor output") else err.split(":")[0])
    kinds.setdefault(key, []).append(r["task_key"])
for kind, ids in sorted(kinds.items()):
    print("   %-64s n=%d" % (kind[:64], len(ids)))
    print("      %s" % ", ".join(sorted(ids)))
    for tid in sorted(ids)[:3]:
        detail = next(r for r in l3_bad if r["task_key"] == tid)
        print("      e.g. %s -> %s" % (tid, detail.get("error", "")[:120]))

print("\n=== L3 resolved: size profile ===")
hdr = "   %-10s %12s %12s %10s %10s %s"
print(hdr % ("task", "in_numel", "out_numel", "peak_f32", "peak_f16", "out_shape"))
for r in sorted(l3_ok, key=lambda x: -x["est_peak_gb"])[:12]:
    print(hdr % (r["task_key"], "%.4g" % r["in_numel"], "%.4g" % r["out_numel"],
                 "%.2f GB" % r["est_peak_gb_float32"],
                 "%.2f GB" % r["est_peak_gb_float16"], r.get("out_shape")))
if l3_ok:
    peaks = sorted(r["est_peak_gb"] for r in l3_ok)
    print("   L3 est_peak_gb: min=%.2f median=%.2f max=%.2f"
          % (peaks[0], peaks[len(peaks) // 2], peaks[-1]))
    print("   L3 units with est_peak >= 60 GB (stage-2 class): %d"
          % sum(1 for r in l3_ok for d in r["dtypes"]
                if r["est_peak_gb_" + d] * 1.3 >= 60.0))

units = [(r["task_key"] + "__" + d, r["est_peak_gb_" + d])
         for r in resolved for d in r["dtypes"]]
print("\ntotal units with a size estimate: %d (live table had %d subjects)"
      % (len(units), len(live_size["subjects"])))

path = SCOPE / "unit_size_table.json"
path.write_text(json.dumps({
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "scope": "250-task draft (L1+L2+L3) -- NOT the live table",
    "source_task_table": str(SCOPE / "task_table.json"),
    "source_contract_draft": str(NEW_DRAFT),
    "cmp_bytes_per_elem_measured": CMP_BYTES_PER_ELEM,
    "subjects": rows}, indent=2), encoding="utf-8")
print("wrote %s" % path)

print("\n=== live files re-verified untouched ===")
again_task = json.loads((OUT / "task_table.json").read_text())
again_size = json.loads((OUT / "unit_size_table.json").read_text())
print("live task_table.json : n_tasks=%d n_units=%d (unchanged: %s)"
      % (again_task["n_tasks"], again_task["n_units"],
         again_task == live_task))
print("live unit_size_table : subjects=%d (unchanged: %s)"
      % (len(again_size["subjects"]), again_size == live_size))
print("A4_SCOPE_BUILT")
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_l3_a4_tables.py")
sftp.close()
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python "
               "-u /root/_l3_a4_tables.py 2>&1", timeout=2400)
c.close()
