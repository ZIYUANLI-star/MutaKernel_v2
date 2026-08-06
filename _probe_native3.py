import _remote as R

py = r"""
import json, os

print('===== robust_kbench highlighted/results.csv =====')
p = '/root/robust_kbench_data/highlighted/results.csv'
print(open(p).read()[:2000])

print()
print('===== highlighted/<task>/ contents =====')
d = '/root/robust_kbench_data/highlighted/layernorm'
for f in sorted(os.listdir(d)):
    fp = os.path.join(d, f)
    print(' ', f, os.path.getsize(fp) if os.path.isfile(fp) else '(dir)')

print()
print('===== KernelBenchX all_records.jsonl: first record keys =====')
p = '/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl'
with open(p) as fh:
    n = 0
    for l in fh:
        r = json.loads(l)
        if n == 0:
            print('keys:', sorted(r.keys()))
            print(json.dumps({k: (str(v)[:150]) for k, v in r.items()},
                             ensure_ascii=False, indent=1)[:2000])
        n += 1
print('total records:', n)

print()
print('===== kernelbenchx_v1.json =====')
m = json.load(open('/root/KernelBenchX_hf/kernelbenchx_v1.json'))
print(type(m).__name__, len(m))
if isinstance(m, list):
    print('sample:', json.dumps(m[0], ensure_ascii=False)[:600])
elif isinstance(m, dict):
    print('keys:', list(m.keys())[:20])

print()
print('===== robust_kbench upstream code: run entry =====')
for f in os.listdir('/root/robust_kbench_data'):
    print(' ', f)
p = '/root/robust_kbench_data/registry.json'
r = json.load(open(p))
print('registry:', json.dumps(r, ensure_ascii=False)[:800])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_native3.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_native3.py",
      timeout=300)
c.close()
print("PROBE_DONE")
