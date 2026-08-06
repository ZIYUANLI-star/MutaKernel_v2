"""Check: (1) are the afternoon -9 units requeued or dead-ended in done?
(2) how long will lane-1 starvation last (pending reserve sizes vs budget)?
(3) any unit stuck in OOM churn (repeated -9 rows)?"""
import _remote as R

probe_py = r"""
import glob, json
from collections import Counter, defaultdict

OUT = '/root/mk_v2_runs/e3_b9_calib'
q = json.load(open(OUT + '/queue_state.json'))
pending = set(q['pending'])
done = set(q['done']) if not isinstance(q['done'], dict) else set(q['done'])

hist = defaultdict(list)
for f in sorted(glob.glob(OUT + '/calibration_v2_lane*.jsonl')):
    for line in open(f):
        if line.strip():
            r = json.loads(line)
            hist[r['unit']].append(r)

# all units whose LATEST row is run_error
latest_err = {u: rs[-1] for u, rs in hist.items()
              if rs[-1]['control_status'] == 'run_error'}
print('units with latest=run_error:', len(latest_err))
for u, r in sorted(latest_err.items()):
    attempts = len(hist[u])
    k9 = sum(1 for x in hist[u] if x.get('exit_code') == -9)
    where = 'PENDING' if u in pending else ('DONE' if u in done else 'CLAIMED?')
    print('  %-28s attempts=%d sigkill=%d state=%s last=%s' % (
        u, attempts, k9, where, r.get('finished_at')))

# pending unit sizes vs remaining budget while L1_P31 runs (105 - 81.9)
units = q['units']
print()
print('pending unit reserve_gb distribution:')
sizes = sorted((units[u].get('reserve_gb') or units[u].get('est_peak_gb') or 0, u)
               for u in pending)
small = [s for s, _ in sizes if s <= 23.1]
print('  fit under 23.1 GB (lane1 while P31 runs):', len(small), 'of', len(sizes))
print('  smallest 5:', [(round(s,1), u) for s, u in sizes[:5]])
print('  largest 5:', [(round(s,1), u) for s, u in sizes[-5:]])

# churn: units with >=2 sigkill rows
churn = {u: rs for u, rs in hist.items()
         if sum(1 for x in rs if x.get('exit_code') == -9) >= 2}
print()
print('units SIGKILLed >=2 times:', len(churn))
for u, rs in churn.items():
    print('  ', u, 'attempts:', len(rs),
          [x.get('control_status') for x in rs])

# claimed unit runtime + estimates
cl = q['claimed']
for uid in cl:
    u = units[uid]
    print()
    print('claimed', uid, 'est_wall fast/slow:',
          u.get('est_wall_s_fast'), '/', u.get('est_wall_s_slow'),
          'timeout:', u.get('unit_timeout_s'),
          'reserve_gb:', u.get('reserve_gb'))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_s2_issue_check.py", "w") as fh:
    fh.write(probe_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _s2_issue_check.py",
      timeout=240)
c.close()
print("ISSUE_CHECK_DONE")
