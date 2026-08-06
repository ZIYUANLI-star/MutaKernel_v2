"""Materialize executable C3 candidates (c3-wrap-v1). Runs ON THE REMOTE.

Each wave-1 C3 subject's raw CUDA kernel (identity: stable_id = sha256 of
normalized CUDA_Code) is wrapped into an importable candidate module that
follows the corpus's own evaluation convention: the parquet ships a
functional reference variant (module_fn + Model(..., fn=module_fn)); the
compiled extension's bound function replaces module_fn via ModelNew.
"""
import hashlib
import json
import re
from pathlib import Path

import pyarrow.parquet as pq


def norm(src):
    lines = [l.rstrip() for l in src.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


reg = json.load(open("/root/mk_v2_runs/e3_corpora/c3_wave1/registry.json"))
want = {s["stable_id"]: s for s in reg["subjects"]}
print("wave-1 C3 subjects:", len(want))

rows_by_sid = {}
for lvl in (1, 2):
    t = pq.read_table(
        "/root/mk_v2/external/C3_ai_cuda_engineer/level_%d.parquet" % lvl)
    for row in t.to_pylist():
        code = row.get("CUDA_Code")
        if not code:
            continue
        sid = hashlib.sha256(norm(code).encode()).hexdigest()
        if sid in want and sid not in rows_by_sid:
            rows_by_sid[sid] = row
print("parquet rows matched:", len(rows_by_sid))
assert set(rows_by_sid) == set(want), "missing rows: %d" % (
    len(set(want) - set(rows_by_sid)))

outdir = Path("/root/mk_v2_runs/e3_corpora/c3_wave1/candidates_wrapped")
outdir.mkdir(parents=True, exist_ok=True)

Q3 = '"' * 3
HDR = (
    Q3 + "E3 C3 candidate wrapper (c3-wrap-v1). Auto-generated; do not edit.\n"
    "\n"
    "raw_kernel_stable_id: {sid}\n"
    "provenance: external/C3_ai_cuda_engineer/level_{lvl}.parquet task {task}\n"
    "adapter: corpus functional variant with fn=<compiled extension>.{bound}\n"
    + Q3 + "\n"
)
BODY = (
    "import torch\n"
    "import torch.nn as nn\n"
    "from torch.utils.cpp_extension import load_inline\n"
    "\n"
    "_CUDA_SRC = {cuda!r}\n"
    "\n"
    "_ext = load_inline(\n"
    "    name=\"c3_{sid16}\",\n"
    "    cpp_sources=\"\",\n"
    "    cuda_sources=[_CUDA_SRC],\n"
    "    verbose=False,\n"
    ")\n"
    "\n"
    "{func}\n"
    "\n"
    "class ModelNew(Model):\n"
    "    def forward(self, *args, **kwargs):\n"
    "        kwargs.pop(\"fn\", None)\n"
    "        return super().forward(*args, fn=_ext.{bound}, **kwargs)\n"
)

manifest_rows = []
bad = []
for sid, s in sorted(want.items(), key=lambda kv: kv[1]["task_key"]):
    row = rows_by_sid[sid]
    cuda = row["CUDA_Code"]
    func = row["PyTorch_Code_Functional"]
    m = re.search(r'm\.def\(\s*"(\w+)"', cuda)
    bound = m.group(1) if m else "forward"
    if "def module_fn" not in func or "fn=module_fn" not in func.replace(" ", ""):
        bad.append((sid[:16], "functional convention"))
        continue
    if "class Model" not in func:
        bad.append((sid[:16], "no Model in functional"))
        continue
    text = (HDR + "\n" + BODY).format(
        sid=sid, sid16=sid[:16], lvl=row["Level_ID"], task=row["Task_ID"],
        cuda=cuda, func=func, bound=bound)
    try:
        compile(text, "<wrapper>", "exec")
    except SyntaxError as exc:
        bad.append((sid[:16], "wrapper syntax: %s" % exc))
        continue
    (outdir / (sid + ".py")).write_text(text, encoding="utf-8")
    manifest_rows.append(sid)

print("wrapped:", len(manifest_rows), "bad:", bad[:5], "n_bad:", len(bad))
assert not bad, "wrapper generation incomplete"

reg["wrapped"] = {
    "adapter": "c3-wrap-v1",
    "dir": str(outdir),
    "note": "raw CUDA kernels wrapped per corpus functional-injection "
            "convention; subject identity in the E3 manifest is the wrapper "
            "hash, raw stable_id kept in metadata",
}
Path("/root/mk_v2_runs/e3_corpora/c3_wave1/registry.json").write_text(
    json.dumps(reg, indent=1), encoding="utf-8")

inp = "/root/mk_v2_runs/e3_campaign/wave1_manifest_input.jsonl"
out = []
for line in open(inp):
    r = json.loads(line)
    if r["dataset"] == "C3":
        sid = r["metadata"]["stable_id"]
        r["candidate_path"] = str(outdir / (sid + ".py"))
        r["metadata"]["adapter"] = "c3-wrap-v1"
    out.append(json.dumps(r))
Path(inp).write_text("\n".join(out) + "\n", encoding="utf-8")
print("manifest input updated")
print("C3_WRAP_OK")
