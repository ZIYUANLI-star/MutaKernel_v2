"""Deep health probe of the running B9 stage-2 calibration."""
import _remote as R

c = R.connect()

probe_py = r"""
import glob, json, os, time
from collections import Counter
from datetime import datetime

OUT = '/root/mk_v2_runs/e3_b9_calib'
q = json.load(open(OUT + '/queue_state.json'))
print('queue: pending', len(q['pending']), 'claimed', len(q['claimed']),
      'done', len(q['done']))
for uid, meta in q['claimed'].items():
    print('  claimed:', uid, '| meta:', json.dumps(meta)[:160])

rows = {}
n_rows = 0
latest_ts = ''
for f in sorted(glob.glob(OUT + '/calibration_v2_lane*.jsonl')):
    for line in open(f):
        if line.strip():
            r = json.loads(line)
            rows[r['unit']] = r
            n_rows += 1
            ts = str(r.get('finished_at', ''))
            if ts > latest_ts:
                latest_ts = ts
print('calibration rows:', n_rows, 'unique units:', len(rows))
print('latest statuses:', dict(Counter(r['control_status'] for r in rows.values())))
print('latest finished_at:', latest_ts)

# recent errors (last 2h)
now = time.time()
recent_err = [r for r in rows.values() if r['control_status'] == 'run_error']
print('run_error units (all-time):', len(recent_err))
for r in sorted(recent_err, key=lambda x: str(x.get('finished_at', '')))[-4:]:
    print('  ', r['unit'], 'exit', r.get('exit_code'), 'at', r.get('finished_at'))

# lane DONE markers + heartbeat
for m in ('B9_CALIB_DONE_LANE0', 'B9_CALIB_DONE_LANE1', 'PAUSED_FOR_SIGNOFF_RERUN'):
    print(m, os.path.exists(OUT + '/' + m))

# guard log tail
logs = sorted(glob.glob(OUT + '/guard_v2*.log') + glob.glob(OUT + '/*.log'),
              key=os.path.getmtime)
if logs:
    lf = logs[-1]
    print('newest log:', lf, 'mtime',
          datetime.fromtimestamp(os.path.getmtime(lf)).isoformat())
    tail = open(lf, errors='replace').read()[-600:]
    print('--- tail ---')
    print(tail)
"""
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_s2_probe_deep.py", "w") as fh:
    fh.write(probe_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _s2_probe_deep.py",
      timeout=240)

print("### processes / gpu / disk / mem")
R.run(c, "ps -eo pid,etime,rss,cmd | grep -E '[b]9_calib|[g]uard_b9|[w]atch' | head -10",
      timeout=60)
R.run(c, "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader; "
         "df -h /root | tail -1; free -g | sed -n 2p", timeout=60)
print("### cgroup memory")
R.run(c, "cat /sys/fs/cgroup/memory.max 2>/dev/null || cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null; "
         "cat /sys/fs/cgroup/memory.current 2>/dev/null", timeout=60)
c.close()
print("DEEP_PROBE_DONE")
