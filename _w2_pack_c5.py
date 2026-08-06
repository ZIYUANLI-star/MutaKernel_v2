"""Package wave-2 C5 candidates locally (raw_sha256-verified) and upload."""
import hashlib
import json
import os
import tarfile
import _remote as R

LOCAL_ROOTS = [
    os.path.join("external", "C5_kernelbench_samples", "baseline_eval"),
    os.path.join("external", "C5_kernelbench_samples", "repeated_sampling"),
]

py = r"""
import json
scope = json.load(open('/root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json'))
want = {s['stable_id'] for s in scope['wave2_subjects'] if s['corpus'] == 'C5'}
rows = []
with open('/root/mk_v2_runs/e2_reconcile/C5_collection_frame.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        if r['stable_id'] in want:
            rows.append({'stable_id': r['stable_id'], 'origin': r['origin'],
                         'raw_sha256': r['raw_sha256'],
                         'task_key': r['task_key'], 'frame_id': r['frame_id']})
print('LISTJSON' + json.dumps(rows))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_w2_c5list.py", "w") as fh:
    fh.write(py)
code, out, err = R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _w2_c5list.py",
                       timeout=120, echo=False)
assert code == 0, err
rows = None
for line in out.splitlines():
    if line.startswith("LISTJSON"):
        rows = json.loads(line[len("LISTJSON"):])
assert rows and len(rows) == 62, f"got {len(rows) if rows else 0}"
print("list fetched:", len(rows))

# package locally
stage = "_w2_c5_pkg"
os.makedirs(os.path.join(stage, "c5_wave2"), exist_ok=True)
registry = []
problems = []
for r in rows:
    rel = r["origin"].replace("\\", os.sep)
    raw = None
    for root in LOCAL_ROOTS:
        src_path = os.path.join(root, rel)
        if not os.path.exists(src_path):
            continue
        blob = open(src_path, "rb").read()
        kern = json.loads(blob).get("kernel")
        if isinstance(kern, str) and hashlib.sha256(
                kern.encode("utf-8")).hexdigest() == r["raw_sha256"]:
            raw = blob
            break
    if raw is None:
        problems.append(("missing_or_hash", r["origin"]))
        continue
    h = r["raw_sha256"]
    d = os.path.join(stage, "c5_wave2", r["stable_id"][:16])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "kernel.json"), "wb") as fh:
        fh.write(raw)
    registry.append({"stable_id": r["stable_id"], "task_key": r["task_key"],
                     "frame_id": r["frame_id"], "raw_sha256": h,
                     "origin": r["origin"]})
print("packaged:", len(registry), "problems:", problems[:5])
assert not problems, "PACKAGING INCOMPLETE"

with open(os.path.join(stage, "c5_wave2", "registry.json"), "w",
          encoding="utf-8") as fh:
    json.dump({"corpus": "C5", "wave": 2, "subject_count": len(registry),
               "source": "local corpus external/C5_kernelbench_samples/"
                         "repeated_sampling, raw_sha256-verified at packaging",
               "subjects": registry}, fh, indent=1)

tar_path = os.path.join(stage, "c5_wave2.tar.gz")
with tarfile.open(tar_path, "w:gz") as tf:
    tf.add(os.path.join(stage, "c5_wave2"), arcname="c5_wave2")
print("tar size:", os.path.getsize(tar_path))

sftp.put(tar_path, "/root/mk_v2/external/c5_wave2.tar.gz")
sftp.close()
R.run(c, "cd /root/mk_v2/external && tar xzf c5_wave2.tar.gz && "
         "mv c5_wave2 C5_kernelbench_samples_wave2 2>/dev/null || true; "
         "ls C5_kernelbench_samples_wave2 | head -3; "
         "ls C5_kernelbench_samples_wave2 | wc -l", timeout=120)
c.close()
print("C5_W2_UPLOAD_DONE")
