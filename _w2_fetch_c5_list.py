"""Fetch wave-2 C5 subject list (stable_id + origin + raw_sha256) to local."""
import json
import _remote as R

py = r"""
import json
scope = json.load(open('/root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json'))
want = {s['stable_id']: s for s in scope['wave2_subjects'] if s['corpus'] == 'C5'}
rows = []
with open('/root/mk_v2_runs/e2_reconcile/C5_collection_frame.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        if r['stable_id'] in want:
            rows.append({'stable_id': r['stable_id'], 'origin': r['origin'],
                         'raw_sha256': r['raw_sha256'],
                         'task_key': r['task_key'],
                         'frame_id': r['frame_id']})
print(json.dumps({'count': len(rows), 'want': len(want), 'rows': rows}))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_w2_c5list.py", "w") as fh:
    fh.write(py)
sftp.close()
out = R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _w2_c5list.py",
            timeout=120)
c.close()
# R.run prints output; also capture from its return if provided
line = out.strip().splitlines()[-1] if isinstance(out, str) and out.strip() else None
if line:
    data = json.loads(line)
    with open("_w2_c5_list.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    print("saved", data["count"], "rows (want", data["want"], ")")
print("FETCH_DONE")
