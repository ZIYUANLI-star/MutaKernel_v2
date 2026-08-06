"""Authoritative ETA via the deployed dry-run planner + corpus mapping + sizes."""
import io

import _remote

SCRIPT = r'''
import json, collections, statistics
from pathlib import Path

draft = Path("/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft.jsonl")
rows = [json.loads(l) for l in draft.read_text().splitlines() if l.strip()]
print("== source_corpora distribution over the 200 tasks")
cc = collections.Counter()
per_corpus_tasks = collections.Counter()
for r in rows:
    sc = r.get("source_corpora")
    key = tuple(sorted(sc)) if isinstance(sc, list) else str(sc)
    cc[key] += 1
    if isinstance(sc, list):
        for x in sc:
            per_corpus_tasks[x] += 1
for k, v in sorted(cc.items(), key=lambda x: -x[1]):
    print("   %-40s %d" % (k, v))
print("   tasks referenced per corpus:", dict(per_corpus_tasks))
print("   sample extraction:", json.dumps(rows[0].get("extraction"))[:300])

ust = json.loads(Path("/root/mk_v2_runs/e3_b9_calib/unit_size_table.json").read_text())
subs = ust["subjects"]
units = []
for s in subs:
    for dt in s["dtypes"]:
        units.append((s["task_key"] + "__" + dt, s.get("est_peak_gb_" + dt, 0.0),
                      s.get("in_numel", 0), s.get("out_numel", 0),
                      s.get("reduction_heavy"), s["task_key"].split("_")[0]))
print("\n== all %d units by est_peak_gb" % len(units))
units.sort(key=lambda x: -x[1])
for u in units[:14]:
    print("   %-28s peak=%7.1f GB  in=%.3e out=%.3e rh=%s" % (u[0], u[1], u[2], u[3], u[4]))
peaks = [u[1] for u in units]
print("   median=%.2f mean=%.2f max=%.1f GB" % (statistics.median(peaks),
                                                statistics.mean(peaks), max(peaks)))
for thr in (10, 30, 50, 84, 100, 120):
    n = sum(1 for p in peaks if p > thr)
    print("   peak > %3d GB: %3d units" % (thr, n))
lv = collections.Counter(u[5] for u in units)
print("   by level:", dict(lv))
rh = collections.Counter(bool(u[4]) for u in units)
print("   reduction_heavy units:", dict(rh))

# heavy-tail / control false-positive quantification from existing rows
OUT = Path("/root/mk_v2_runs/e3_b9_calib")
crows = {}
for p in sorted(OUT.glob("calibration_*lane*.jsonl")):
    for line in p.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            crows[r["unit"]] = r
print("\n== control outcome census (%d rows)" % len(crows))
st = collections.Counter(r["control_status"] for r in crows.values())
print("  ", dict(st))
print("== heavy_tail detail")
for u, r in sorted(crows.items()):
    if r["control_status"] == "calibrated_heavy_tail":
        print("   %-24s tol=%s max_abs=%s pass_rate=%s dtype=%s"
              % (u, r.get("calibrated_tol"), r.get("control_max_abs"),
                 r.get("control_pass_rate_at_tol"), r.get("dtype")))
print("== controls_incomplete detail")
for u, r in sorted(crows.items()):
    if r["control_status"] == "controls_incomplete":
        print("   %-24s kinds=%s dtype=%s" % (u, r.get("outcome_kinds"), r.get("dtype")))
print("== failures to requeue")
for u, r in sorted(crows.items()):
    if r["control_status"] not in ("calibrated_ok", "calibrated_heavy_tail",
                                   "controls_incomplete"):
        print("   %-24s status=%s exit=%s wall=%s"
              % (u, r["control_status"], r.get("exit_code"), r.get("wall_s")))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_h5a.py")
sftp.close()
print("#### scope + sizes + control census")
_remote.run(c, "/root/miniconda3/bin/python /root/_h5a.py", timeout=300)
print("\n#### resume_b9.sh --dry-run (read-only: plan + ETA, starts nothing)")
_remote.run(c, "cd /root/mk_v2_runs/e3_b9_calib && bash resume_b9.sh --dry-run 2>&1",
            timeout=600)
c.close()
print("\nH5_DONE")
