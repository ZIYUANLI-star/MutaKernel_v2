"""Detail the first campaign observations."""
import _remote as R

py = r"""
import json
OUT = '/root/mk_v2_runs/e3_campaign'
rows = [json.loads(l) for l in open(OUT + '/lane_m_run/observations.jsonl')]
for r in rows:
    w = r['worker_result']
    print('=' * 72)
    print(r['subject_id'], '|', r['strategy_name'], r['policy'], r['mode'],
          '->', r['validation_status'], '| phase', w.get('phase'),
          '| wall %.0fs' % (r['parent_wall_ms'] / 1000))
    print('reason:', str(w.get('reason'))[:160])
    for err in (w.get('errors') or [])[:1]:
        print('err:', json.dumps(err)[:260])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_incd.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_incd.py",
      timeout=120)
c.close()
print("INC_DETAIL_DONE")
