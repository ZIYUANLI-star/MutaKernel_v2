"""Is the torch extension cache being reused across cases?"""
import _remote as R

py = r"""
import os, glob, json
from collections import Counter

base = '/root/mk_v2_runs/e3_campaign/lane_m_run'
# every build dir = one actual compile
builds = glob.glob(base + '/torch_extensions/*/*/build.ninja')
print('build dirs (actual compiles):', len(builds))
so = glob.glob(base + '/torch_extensions/*/*/*.so')
print('.so files:', len(so))
# distinct subject-level extension names
names = Counter(p.split('/')[-2] for p in builds)
print('distinct ext names:', len(names), ' max rebuilds per name:',
      names.most_common(3))
# top-level dirs (per-case scatter?)
tops = set(p.split('/torch_extensions/')[-1].split('/')[0] for p in builds)
print('top-level cache dirs:', len(tops), list(sorted(tops))[:5])

# C3 obs count for comparison
n_c3 = 0
for f in glob.glob('/root/mk_v2_runs/e3_campaign/**/observations.jsonl',
                   recursive=True):
    for line in open(f):
        if line.strip() and json.loads(line).get('dataset') == 'C3':
            n_c3 += 1
print('C3 observations:', n_c3)

# sample worker log: does it show compile on a non-first case?
logs = sorted(glob.glob(base + '/worker_logs/*.log'), key=os.path.getmtime)
if logs:
    tail = open(logs[-1], errors='replace').read()
    for kw in ('Building extension', 'ninja', 'No modifications detected',
               'Loading extension'):
        if kw in tail:
            print('last worker log contains:', kw)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_lm_cache.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _lm_cache.py",
      timeout=180)
c.close()
print("CACHE_CHECK_DONE")
