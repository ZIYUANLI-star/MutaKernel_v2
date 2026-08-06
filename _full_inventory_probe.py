"""Full remote data inventory + Lane M live status for expectation assessment."""
import _remote as R

py = r"""
import json, glob, os, subprocess, time
from collections import Counter

print('=== 1. Lane M campaign live status ===')
out = subprocess.run(['pgrep', '-af', 'run_fse_[e]xperiment'],
                     capture_output=True, text=True).stdout.strip()
print('runner procs:', out or 'NONE')
gz = subprocess.run(['pgrep', '-af', '[g]uard_lane_m'],
                    capture_output=True, text=True).stdout.strip()
print('guard procs:', gz or 'NONE')
sq = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used',
                     '--format=csv,noheader'], capture_output=True, text=True)
print('gpu:', sq.stdout.strip())

base = '/root/mk_v2_runs/e3_campaign'
obs_files = sorted(glob.glob(base + '/**/observations.jsonl', recursive=True))
total = 0
oc = Counter()
subj = set()
newest = 0
lat = []
for f in obs_files:
    for line in open(f):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        total += 1
        oc[d.get('outcome') or d.get('status')] += 1
        subj.add(d.get('subject_id') or d.get('subject'))
        w = d.get('wall_ms')
        if w:
            lat.append(w)
    m = os.path.getmtime(f)
    newest = max(newest, m)
print('obs files:', len(obs_files), 'total obs:', total)
print('outcomes:', dict(oc.most_common()))
print('distinct subjects touched:', len(subj))
if lat:
    lat.sort()
    print('wall_ms median:', lat[len(lat)//2], 'p95:', lat[int(len(lat)*0.95)])
print('newest obs file age (s):', int(time.time() - newest) if newest else 'n/a')

# guard log tail
logs = sorted(glob.glob(base + '/*.log'), key=os.path.getmtime)
if logs:
    L = logs[-1]
    print('latest log:', L)
    lines = open(L, errors='replace').readlines()
    print(''.join(lines[-6:]))

print('=== 2. closed dataset inventory ===')
inv = [
    ('E0 run5', '/root/mk_v2_runs/e0_run5_s0/observations.jsonl'),
    ('E1 baseline', '/root/mk_v2_runs/e1/baseline_observations.jsonl'),
    ('E1 equiv summary', '/root/mk_v2_runs/e1/equiv_summary.json'),
    ('E1 amendment', '/root/mk_v2_runs/e1/amendment_v1/amendment_manifest.json'),
    ('B9 calib final', '/root/mk_v2_runs/e3_b9_calib/b9_calib_final_summary.json'),
    ('escape mechs', '/root/mk_v2_runs/e1/escape_mechanisms.json'),
    ('crossfit final', '/root/mk_v2_runs/e1/analysis/final'),
]
for name, p in inv:
    if os.path.isdir(p):
        print(f'{name}: DIR {len(os.listdir(p))} entries')
    elif os.path.exists(p):
        print(f'{name}: {os.path.getsize(p)} bytes')
    else:
        print(f'{name}: MISSING')
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_inv_probe.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _inv_probe.py",
      timeout=300)
c.close()
print("INVENTORY_DONE")
