"""Feasibility probe: (1) legacy-oracle offline re-grade, (2) equal-time
truncation, (3) M-dir inputs coverage, (4) run_ablation semantics,
(5) B9 calib coverage vs 653 subjects."""
import _remote as R

py = r"""
import json, os, glob
from collections import Counter

camp = '/root/mk_v2_runs/e3_campaign'
run = camp + '/lane_m_run'

print('===== 1. evidence schema: does a PASS record keep raw error magnitudes? =====')
n_pass = n_fail = 0
pass_ev = fail_ev = None
with open(run + '/observations.jsonl') as f:
    for l in f:
        r = json.loads(l)
        wr = r.get('worker_result') or {}
        killed = wr.get('killed')
        if killed and fail_ev is None:
            fail_ev = wr
        if killed is False and pass_ev is None:
            pass_ev = wr
        if pass_ev is not None and fail_ev is not None:
            break

def show(tag, wr):
    print('--- %s ---' % tag)
    ev = wr.get('evidence')
    print('evidence type:', type(ev).__name__)
    s = json.dumps(ev)[:1200]
    print(s)
    print('timings_ms:', json.dumps(wr.get('timings_ms'))[:300])

show('PASS sample', pass_ev)
show('FAIL sample', fail_ev)

print()
print('===== 2. per-case wallclock available in every obs? =====')
missing_t = 0; total = 0
with open(run + '/observations.jsonl') as f:
    for l in f:
        r = json.loads(l)
        total += 1
        t = (r.get('worker_result') or {}).get('timings_ms')
        if not t:
            missing_t += 1
print('obs total %d, missing timings %d' % (total, missing_t))

print()
print('===== 3. M-dir inputs: map + fingerprints for wave-1 subjects =====')
maps = glob.glob('/root/mk_v2_runs/e1/**/fault_to_stress_map*.json', recursive=True) + \
       glob.glob('/root/mk_v2_runs/e1/fault_to_stress_map*.json')
for m in sorted(set(maps)):
    print(' map:', m, os.path.getsize(m))
fps = glob.glob('/root/mk_v2_runs/**/site_fingerprint*', recursive=True)[:5]
print(' fingerprint artifacts (first 5):', fps)
# does src.validator have fingerprint generator?
for f in glob.glob('/root/mk_v2/src/validator/*.py'):
    print(' src/validator:', os.path.basename(f))

print()
print('===== 4. run_ablation.py semantics =====')
src = open('/root/mk_v2/scripts/run_ablation.py').read()
print(src[:2500])

print()
print('===== 5. B9 calib coverage vs wave-1 subjects =====')
calib = json.load(open('/root/mk_v2_runs/e3_b9_calib/b9_calib_final_summary.json'))
print('calib summary keys:', list(calib.keys())[:10])
units = calib.get('units') or calib.get('records') or []
print('calib units:', len(units) if isinstance(units, list) else 'dict %d' % len(units))
subs = json.load(open(camp + '/wave1_subject_manifest_v2.json'))
slist = subs.get('subjects') or subs
print('wave1 subjects:', len(slist))
if isinstance(slist, list) and slist and isinstance(slist[0], dict):
    print('subject sample keys:', list(slist[0].keys()))
    tasks = set()
    for s in slist:
        tasks.add(s.get('task_id'))
    print('distinct task_ids:', len(tasks), 'sample:', sorted(list(tasks))[:5])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_feas_probe.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _feas_probe.py",
      timeout=600)
c.close()
print("FEAS_DONE")
