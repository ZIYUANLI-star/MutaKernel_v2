# -*- coding: utf-8 -*-
"""Upload the extended reconcile script, run C3 reconciliation remotely, fetch outputs."""
import os
import _remote as R

c = R.connect()
sftp = c.open_sftp()

# Single-file put (never tar over the tree; e1 is running).
sftp.put("scripts/reconcile_corpora.py", "/root/mk_v2/scripts/reconcile_corpora.py")
print("uploaded reconcile_corpora.py")

R.run(c, "mkdir -p /root/mk_v2_runs/e2_reconcile", timeout=30)
code, out, err = R.run(
    c,
    "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
    "scripts/reconcile_corpora.py --external-root external "
    "--out-dir /root/mk_v2_runs/e2_reconcile --corpora C3",
    timeout=900,
)
if code != 0:
    raise SystemExit("remote C3 reconcile failed")

local_dir = os.path.join("MutakernelV2", "实验", "补充实验数据", "collection_frames")
for name in ("C3_collection_frame.jsonl", "C3_subject_frame.jsonl",
             "collection_frames.freeze.json"):
    remote = f"/root/mk_v2_runs/e2_reconcile/{name}"
    local = os.path.join(local_dir, "_remote_" + name)
    sftp.get(remote, local)
    print("fetched", name, "->", local)

sftp.close()
c.close()
print("C3_REMOTE_DONE")
