"""Quick final probe: obs mix + rate since ignition."""
import _remote as R

py = r"""
import collections, json
OUT = '/root/mk_v2_runs/e3_campaign'
rows = [json.loads(l) for l in open(OUT + '/lane_m_run/observations.jsonl')]
print('obs:', len(rows))
print('statuses:', dict(collections.Counter(r['validation_status'] for r in rows)))
print('by corpus:', dict(collections.Counter(
    (r['subject_id'][:2], r['validation_status']) for r in rows)))
w = [r['parent_wall_ms'] for r in rows]
print('median wall ms:', sorted(w)[len(w)//2] if w else None)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_fprobe.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_fprobe.py",
      timeout=120)
R.run(c, "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader",
      timeout=60)
c.close()
print("FINAL_PROBE_DONE")
