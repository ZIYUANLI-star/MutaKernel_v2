import _remote as R

py = r"""
import json, os, glob

print('===== KernelBench repo root (L3 refs) =====')
for cand in ('/root/KernelBench', '/root/mk_v2/external/KernelBench',
             '/root/mk_v2/KernelBench'):
    if os.path.isdir(cand):
        print(cand, '->', sorted(os.listdir(cand))[:15])
hits = glob.glob('/root/**/KernelBench/level3', recursive=True)[:5] + \
       glob.glob('/root/**/level_3', recursive=True)[:8]
for h in hits:
    if '/proc/' in h: continue
    print(' hit:', h)

print()
print('===== collection frames (reconcile output) =====')
for d in glob.glob('/root/mk_v2_runs/e2_reconcile/*'):
    print(' ', d, os.path.getsize(d) if os.path.isfile(d) else '(dir)')

print()
print('===== c3 materialize / wrapped: how built =====')
d = '/root/mk_v2_runs/e3_corpora/c3_materialize'
print(d, '->', sorted(os.listdir(d))[:10])
d = '/root/mk_v2_runs/e3_corpora/c3_wave1/candidates_wrapped'
fs = sorted(os.listdir(d))
print(d, 'count', len(fs), 'sample', fs[:3])

print()
print('===== find the wrapper / staging scripts used for wave1 corpora =====')
for pat in ('/root/mk_v2/_*wrap*', '/root/mk_v2/_*stage*', '/root/mk_v2/_*corp*',
            '/root/mk_v2/_*materialize*', '/root/mk_v2/_*wave1*'):
    for h in glob.glob(pat):
        if h.endswith('.pyc'): continue
        print(' ', h)

print()
print('===== wave1 manifest jsonl input (spec) exists? =====')
for h in glob.glob('/root/mk_v2_runs/e3_campaign/*.jsonl'):
    print(' ', h, os.path.getsize(h))

print()
print('===== C5 corpus source (HF?) =====')
d = '/root/mk_v2/external/C5_kernelbench_samples_wave1'
subs = sorted(os.listdir(d))
print('c5 wave1 dirs:', len(subs))
s0 = os.path.join(d, subs[0])
print(s0, '->', sorted(os.listdir(s0)))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_w2a.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_w2a.py",
      timeout=300)
c.close()
print("PROBE_DONE")
