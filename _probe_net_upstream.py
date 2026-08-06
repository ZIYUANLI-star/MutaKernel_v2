import _remote as R

py = r"""
import json, os, glob, subprocess

print('===== wave2 counts =====')
s = json.load(open('/root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json'))
print('counts:', json.dumps(s['counts'], indent=1))
print('decision:', json.dumps(s['decision'], ensure_ascii=False, indent=1)[:2000])
from collections import Counter
c = Counter(x['corpus'] for x in s['wave2_subjects'])
print('wave2 by corpus:', dict(c))
kk = Counter(x['task_key'].split('_P')[0] for x in s['wave2_subjects'])
print('wave2 task levels:', dict(kk))

print()
print('===== search for upstream repos anywhere =====')
for pat in ('/root/**/robust-kbench*', '/root/**/robust_kbench*',
            '/root/**/KernelBenchX*', '/root/**/kernelbenchx_v1.json'):
    for h in glob.glob(pat, recursive=True)[:10]:
        if '__pycache__' in h or '/proc/' in h:
            continue
        print(' ', h)

print()
print('===== network check =====')
for host in ('github.com', 'hf-mirror.com'):
    r = subprocess.run(['timeout', '8', 'bash', '-c',
                        f'curl -sI https://{host} | head -1'],
                       capture_output=True, text=True)
    print(host, '->', (r.stdout or r.stderr).strip()[:120])

print()
print('===== gpuemu native tool presence =====')
g = '/root/mk_v2/external/C6_gpuemu/gpuemu'
for dp, dn, fn in os.walk(g):
    depth = dp.replace(g, '').count('/')
    if depth <= 1:
        print(dp.replace(g, 'gpuemu'), '->', sorted(fn)[:10])
    if depth > 1:
        dn[:] = []
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_net.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_net.py",
      timeout=300)
c.close()
print("PROBE_DONE")
