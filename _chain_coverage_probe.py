"""Inventory remote experiment chain vs blueprint placeholders."""
import _remote as R

py = r"""
import json, os, glob, subprocess, time

base = '/root/mk_v2_runs'
camp = base + '/e3_campaign'

print('=== 1. running processes ===')
out = subprocess.run(['bash', '-c',
    "ps aux | grep -E 'run_fse|guard|mutant_worker|calib|b7|b8|b9|mdir|m_dir' | grep -v grep"],
    capture_output=True, text=True).stdout
print(out or '(none)')

print('=== 2. lane M progress ===')
run = camp + '/lane_m_run'
obs_n = sum(1 for l in open(run + '/observations.jsonl') if l.strip())
plan = json.load(open(camp + '/wave1_lane_m_plan_v2.json'))
cases = plan.get('cases') or plan.get('test_cases') or []
print('obs:', obs_n, '/ plan cases:', len(cases))
# verdict split + skipped
from collections import Counter
verd = Counter(); strat = Counter()
last_ts = None
with open(run + '/observations.jsonl') as f:
    for l in f:
        r = json.loads(l)
        verd[r.get('verdict')] += 1
        last_ts = r.get('timestamp') or last_ts
print('verdicts:', dict(verd))
print('last obs ts:', last_ts)

print('=== 3. what executors/scripts exist in /root/mk_v2/scripts ===')
for f in sorted(os.listdir('/root/mk_v2/scripts')):
    print(' ', f)

print('=== 4. port-side assets ===')
for pat in ['/root/mk_v2/src/baselines', '/root/mk_v2/baselines',
            '/root/mk_v2/src/ports']:
    if os.path.isdir(pat):
        for dp, dn, fn in os.walk(pat):
            for f in fn:
                print(' ', os.path.join(dp, f))

print('=== 5. b9 calib / c6 / other corpora assets under mk_v2_runs ===')
for d in sorted(os.listdir(base)):
    p = os.path.join(base, d)
    if os.path.isdir(p):
        n = len(os.listdir(p))
        print(' ', d, '(%d entries)' % n)

print('=== 6. strategy matrix roles (which validator rows are runnable by our runner) ===')
sm = glob.glob('/root/mk_v2/**/fse_strategy_matrix*.json', recursive=True)
for f in sm:
    j = json.load(open(f))
    names = None
    if isinstance(j, dict):
        for k in ('strategies', 'matrix', 'rows'):
            if k in j:
                names = j[k]
    print(f)
    if isinstance(names, dict):
        print('  keys:', list(names.keys()))
    elif isinstance(names, list):
        print('  items:', [x.get('id', x.get('name')) if isinstance(x, dict) else x for x in names][:20])

print('=== 7. does plan include which strategy ids? ===')
sids = Counter()
for c in cases[:200000]:
    sids[c.get('strategy_id') or c.get('strategy')] += 1
print(dict(sids))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_chain_probe.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _chain_probe.py",
      timeout=600)
c.close()
print("CHAIN_PROBE_DONE")
