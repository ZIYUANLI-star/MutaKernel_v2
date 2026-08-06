"""Probe: (1) native dataset assets for B7/B8/B9 ports, (2) C2 wave-2
subject manifest / corpus size, (3) published-result files for port fidelity."""
import _remote as R

py = r"""
import json, os, glob

print('===== 1. external/ tree (top 2 levels) =====')
for root in ('/root/mk_v2/external', '/root/mk_v2_runs/external'):
    if not os.path.isdir(root):
        print(root, 'MISSING')
        continue
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if os.path.isdir(p):
            subs = sorted(os.listdir(p))[:12]
            print(f'{p}/ -> {subs}')
        else:
            print(p, os.path.getsize(p))

print()
print('===== 2. search for robust-kbench / kernelbenchx / native assets =====')
hits = []
for pat in ('robust*', '*kbench*', '*KernelBenchX*', '*kernelbenchx*',
            '*native*'):
    hits += glob.glob('/root/mk_v2/external/**/' + pat, recursive=True)[:20]
    hits += glob.glob('/root/mk_v2/**/' + pat, recursive=True)[:20]
for h in sorted(set(hits))[:40]:
    print(' ', h)

print()
print('===== 3. wave2 manifests =====')
for pat in ('/root/mk_v2_runs/e3_campaign/*wave2*',
            '/root/mk_v2_runs/e3_campaign/*w2*',
            '/root/mk_v2_runs/**/wave2*'):
    for h in glob.glob(pat, recursive=True):
        print(' ', h, os.path.getsize(h) if os.path.isfile(h) else '(dir)')

print()
print('===== 4. corpora manifest: which corpora + counts =====')
for mf in glob.glob('/root/mk_v2_runs/e3_corpora/*.json')[:10]:
    print(' ', mf, os.path.getsize(mf))
p = '/root/mk_v2_runs/e3_corpora'
if os.path.isdir(p):
    for d in sorted(os.listdir(p)):
        print('  e3_corpora/', d)

print()
print('===== 5. wave1 manifest corpus split =====')
m = json.load(open('/root/mk_v2_runs/e3_campaign/wave1_subject_manifest_v2.json'))
from collections import Counter
c = Counter()
for s in m['subjects']:
    c[s.get('corpus') or s.get('corpus_id') or s['subject_id'].split('_')[0]] += 1
print('wave1 subjects by corpus:', dict(c))
print('total:', len(m['subjects']))

print()
print('===== 6. any full corpus manifest with wave2 candidates =====')
for f in glob.glob('/root/mk_v2_runs/e3_campaign/*.json'):
    sz = os.path.getsize(f)
    print(' ', f, sz)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_nw2.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_nw2.py",
      timeout=300)
c.close()
print("PROBE_DONE")
