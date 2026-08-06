import _remote as R

py = r"""
import json

print('===== scope v1: corpora + waves =====')
s = json.load(open('/root/mk_v2_runs/e3_campaign/e3_campaign_scope_v1.json'))
print('top keys:', list(s.keys()))
for k, v in s.items():
    if isinstance(v, (str, int, float)):
        print(' ', k, '=', v)
    elif isinstance(v, dict):
        print(' ', k, ': dict keys', list(v.keys())[:15])
    elif isinstance(v, list):
        print(' ', k, ': list len', len(v),
              'sample', json.dumps(v[0])[:200] if v else '')

# dig into wave / corpus info
for k in ('waves', 'corpora', 'wave2', 'scope'):
    v = s.get(k)
    if v is not None:
        print()
        print('---', k, '---')
        print(json.dumps(v, ensure_ascii=False, indent=1)[:3000])

print()
print('===== port module provenance headers =====')
for f in ('/root/mk_v2/src/experiments/external_ports/b7_robust_kbench.py',
          '/root/mk_v2/src/experiments/external_ports/b8_kernelbenchx.py',
          '/root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py'):
    print('---', f, '---')
    src = open(f).read()
    print(src[:1500])
    print()
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_sp.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_sp.py",
      timeout=300)
c.close()
print("PROBE_DONE")
