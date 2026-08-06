"""Lane M deep probe: real schema, throughput timeline, GPU duty cycle."""
import _remote as R

py = r"""
import json, glob, os, time, subprocess
from collections import Counter

base = '/root/mk_v2_runs/e3_campaign'
obs_files = sorted(glob.glob(base + '/**/observations.jsonl', recursive=True))
rows = []
for f in obs_files:
    for line in open(f):
        if line.strip():
            rows.append(json.loads(line))
print('total obs:', len(rows))
r0 = rows[-1]
print('fields:', sorted(r0.keys()))
for k in ('verdict', 'result', 'grade', 'status', 'outcome', 'case_verdict'):
    vc = Counter(str(r.get(k)) for r in rows)
    if set(vc) != {'None'}:
        print(k, ':', dict(vc.most_common()))

# throughput timeline by finished_at (30-min bins)
ts = []
for r in rows:
    t = r.get('finished_at') or r.get('timestamp')
    if t:
        ts.append(t)
ts.sort()
if ts:
    print('first obs:', ts[0], ' last obs:', ts[-1])
    bins = Counter(t[:15] for t in ts)  # 10-min granularity via prefix
    for k in sorted(bins)[-12:]:
        print(' ', k, bins[k])

# per-subject progress
subj = Counter()
strat = Counter()
for r in rows:
    subj[r.get('subject_id') or r.get('subject')] += 1
    strat[r.get('strategy') or r.get('strategy_id')] += 1
print('subjects:', len(subj), 'strategies:', dict(strat.most_common()))
print('top subjects:', subj.most_common(5))

# GPU duty cycle over 30s
samples = []
for _ in range(10):
    q = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used',
                        '--format=csv,noheader,nounits'],
                       capture_output=True, text=True).stdout.strip()
    samples.append(q)
    time.sleep(3)
print('gpu samples (util%, memMiB):', samples)

# runner log tail
logs = sorted(glob.glob(base + '/lane_m_run*/*.log') + glob.glob(base + '/*.log'),
              key=os.path.getmtime)
for L in logs[-2:]:
    print('--- tail', L)
    print(''.join(open(L, errors='replace').readlines()[-8:]))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_lm_deep.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _lm_deep.py",
      timeout=300)
c.close()
print("DEEP_PROBE_DONE")
