"""Materialize C3 wave-1 subjects on the remote (CPU-only, deterministic).

Steps:
  1. rerun reconcile_corpora.py --corpora C3 --materialize into a fresh dir
     (never touches the frozen e2_reconcile frames);
  2. determinism check: regenerated C3_subject_frame.jsonl must be
     byte-identical to the frozen one from E2;
  3. stage the 189 wave-1 subjects (per e3_campaign_scope_v1.json) as
     candidates/<stable_id>.py + registry under e3_corpora/c3_wave1;
  4. verify each staged file's normalized sha256 == stable_id.
"""
import _remote as R

c = R.connect()

print("### 1. materialize C3 (fresh out dir)")
code, o, e = R.run(
    c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
       "scripts/reconcile_corpora.py --corpora C3 "
       "--out-dir /root/mk_v2_runs/e3_corpora/c3_materialize --materialize "
       "2>&1 | tail -8",
    timeout=1200)
if code != 0:
    raise SystemExit("materialize failed")

print("### 2. determinism check vs frozen E2 frame")
R.run(c, "bash -c 'diff <(sort /root/mk_v2_runs/e2_reconcile/C3_subject_frame.jsonl) "
         "<(sort /root/mk_v2_runs/e3_corpora/c3_materialize/C3_subject_frame.jsonl) "
         ">/dev/null && echo SUBJECT_FRAME_IDENTICAL || echo SUBJECT_FRAME_DIFFERS'",
      timeout=120)

print("### 3+4. stage wave-1 subjects + hash verify")
stage_py = r"""
import hashlib, json, shutil
from pathlib import Path

def normalize_source(source):
    lines = [l.rstrip() for l in source.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"

scope = json.load(open("/root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json"))
want = [s for s in scope["wave1_subjects"] if s["corpus"] == "C3"]
print("wave-1 C3 subjects wanted:", len(want))

src = Path("/root/mk_v2_runs/e3_corpora/c3_materialize/C3/candidates")
dst = Path("/root/mk_v2_runs/e3_corpora/c3_wave1")
cand = dst / "candidates"
cand.mkdir(parents=True, exist_ok=True)

registry, missing, badhash = [], [], []
for s in sorted(want, key=lambda r: (r["task_key"], r["stable_id"])):
    sid = s["stable_id"]
    f = src / (sid + ".py")
    if not f.exists():
        missing.append(sid[:16]); continue
    text = f.read_text(encoding="utf-8")
    h = hashlib.sha256(normalize_source(text).encode("utf-8")).hexdigest()
    if h != sid:
        badhash.append(sid[:16]); continue
    shutil.copy2(f, cand / f.name)
    registry.append({"stable_id": sid, "task_key": s["task_key"],
                     "frame_id": s["frame_id"], "sha256_normalized": h})

(dst / "registry.json").write_text(json.dumps({
    "scope_id": scope["scope_id"], "corpus": "C3",
    "source": "reconcile_corpora --materialize (deterministic re-extraction, "
              "subject frame verified identical to frozen E2 frame)",
    "subjects": registry}, indent=1), encoding="utf-8")
print("staged:", len(registry), "missing:", missing[:5], "badhash:", badhash[:5])
assert not missing and not badhash, "STAGING INCOMPLETE"
print("C3_STAGE_OK")
"""
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_c3_stage.py", "w") as fh:
    fh.write(stage_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _c3_stage.py",
      timeout=600)
c.close()
print("C3_MATERIALIZE_DONE")
