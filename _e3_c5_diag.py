"""Diagnose the C5 inconclusive worker cases."""
import _remote as R

py = r"""
import json
from pathlib import Path

OUT = Path('/root/mk_v2_runs/e3_campaign/lane_m_smoke_c5')
rows = [json.loads(l) for l in open(OUT / 'observations.jsonl')]
for r in rows[:3]:
    w = r['worker_result']
    print('=' * 70)
    print(r['policy'], r['mode'], r['validation_status'], 'phase', w.get('phase'))
    print('reason:', w.get('reason'))
    for err in (w.get('errors') or [])[:2]:
        print('err:', json.dumps(err)[:300])
    log = w.get('evidence', {}).get('worker_log', {}).get('logical_path')
    if log:
        p = OUT / log
        if p.exists():
            txt = p.read_text(errors='replace')
            print('--- worker log tail ---')
            print(txt[-1200:])
    break
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_c5diag.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_c5diag.py",
      timeout=120)
c.close()
print("C5_DIAG_DONE")
