"""Materialize executable C3 candidates (c3-wrap-v1) + rebuild manifest/plan.

Each wave-1 C3 subject's raw CUDA kernel (identity: stable_id = sha256 of
normalized CUDA_Code) is wrapped into an importable candidate module that
follows the corpus's own evaluation convention: the parquet ships a
functional reference variant (module_fn + Model(fn=module_fn)); the compiled
extension's bound function replaces module_fn. ModelNew subclasses that
functional Model and injects fn=_ext.<bound>.

Wrapper embeds CUDA_Code and PyTorch_Code_Functional verbatim (audit), records
stable_id + parquet provenance in the header. Subject identity for the E3
manifest is the wrapper file hash; the raw-kernel stable_id stays in metadata.
"""
import _remote as R

gen_py = r'''
import hashlib, json, re
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

TPL = '''"""E3 C3 candidate wrapper (c3-wrap-v1). Auto-generated; do not edit.

raw_kernel_stable_id: {sid}
provenance: external/C3_ai_cuda_engineer/level_{lvl}.parquet task {task}
adapter: corpus functional variant with fn=<compiled extension>.{bound}
"""
import torch
import torch.nn as nn
from torch.utils.cpp_extension import load_inline

_CUDA_SRC = {cuda!r}

_ext = load_inline(
    name="c3_{sid16}",
    cpp_sources="",
    cuda_sources=[_CUDA_SRC],
    verbose=False,
)

{func}

class ModelNew(Model):
    def forward(self, *args, **kwargs):
        kwargs.pop("fn", None)
        return super().forward(*args, fn=_ext.{bound}, **kwargs)
'''

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
    text = TPL.format(sid=sid, sid16=sid[:16], lvl=row["Level_ID"],
                      task=row["Task_ID"], cuda=cuda, func=func, bound=bound)
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

# rebuild manifest input with wrapped candidate paths for C3
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
'''

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_c3wrap.py", "w") as fh:
    fh.write(gen_py)
sftp.close()
code, o, e = R.run(c, f"cd /root/mk_v2 && {P} -u _e3_c3wrap.py", timeout=1200)
if code != 0:
    raise SystemExit("wrapper generation failed")

# rebuild manifest + plan v2 + env (with nvcc on PATH)
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/build_fse_subject_manifest.py "
       f"--root / --input {OUT}/wave1_manifest_input.jsonl "
       f"--output {OUT}/wave1_subject_manifest_v2.json", timeout=900)
if code != 0:
    raise SystemExit("manifest v2 failed")
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/plan_fse_experiment.py "
       f"--subjects {OUT}/wave1_subject_manifest_v2.json "
       "--strategy-matrix configs/fse_e3_wave1_matrix.json "
       f"--output {OUT}/wave1_lane_m_plan_v2.json", timeout=1800)
if code != 0:
    raise SystemExit("plan v2 failed")
R.run(c, f"rm -f {OUT}/wave1_environment.json", timeout=30)
code, o, e = R.run(
    c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
       f"{P} -u scripts/capture_fse_environment.py "
       f"--output {OUT}/wave1_environment.json", timeout=600)
R.run(c, f"{P} -c \"import json;"
         f"g=json.load(open('{OUT}/wave1_environment.json'));"
         "print('commit', g['git']['commit'][:12], 'dirty', g['git']['dirty'],"
         " 'nvcc', g['nvcc']['status'])\"", timeout=60)
c.close()
print("C3_WRAP_BUILD_DONE")
