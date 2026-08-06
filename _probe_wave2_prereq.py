import _remote as R

py = r"""
import json, os, glob

print('===== scripts that build subject manifests =====')
for f in sorted(glob.glob('/root/mk_v2/scripts/*.py')):
    print(' ', os.path.basename(f))

print()
print('===== wave1 manifest: how a subject looks =====')
m = json.load(open('/root/mk_v2_runs/e3_campaign/wave1_subject_manifest_v2.json'))
print('top keys:', list(m.keys()))
s0 = m['subjects'][0]
print('subject keys:', sorted(s0.keys()))
for k in ('subject_id', 'corpus', 'task_key', 'contract_id', 'contract_status',
          'contract_review'):
    if k in s0:
        print(' ', k, '=', str(s0[k])[:120])

print()
print('===== contracts store: any L3 contracts? =====')
hits = glob.glob('/root/mk_v2_runs/**/contract*', recursive=True)
seen = set()
for h in hits:
    d = os.path.dirname(h)
    if d in seen: continue
    seen.add(d)
    print(' ', h if os.path.isfile(h) else h + '/')
    if len(seen) > 15: break

print()
print('===== does the manifest builder exist + args =====')
for name in ('build_subject_manifest.py', 'plan_fse_experiment.py',
             'build_wave_manifest.py', 'freeze_contracts.py',
             'contract_review_report.py'):
    p = '/root/mk_v2/scripts/' + name
    if os.path.exists(p):
        src = open(p).read()
        print('---', name, '---')
        for line in src.splitlines():
            ls = line.strip()
            if 'add_argument' in ls and len(ls) < 140:
                print('   ', ls)

print()
print('===== L3 task frames present in corpora dirs? =====')
for d in ('/root/mk_v2_runs/e3_corpora/c3_wave1', '/root/mk_v2_runs/e3_corpora/c5_wave1'):
    fs = sorted(os.listdir(d))[:10]
    print(d, '->', fs)

print()
print('===== b9 calib driver location =====')
for h in glob.glob('/root/mk_v2*/**/*b9_calib*', recursive=True)[:10]:
    print(' ', h)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_w2p.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_w2p.py",
      timeout=300)
c.close()
print("PROBE_DONE")
