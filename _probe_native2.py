import _remote as R

py = r"""
import json, os, glob

def tree(root, depth=1):
    if not os.path.isdir(root):
        print(root, 'MISSING'); return
    for dp, dn, fn in os.walk(root):
        d = dp.replace(root, '').count('/')
        if d <= depth:
            print(dp, '->', sorted(dn)[:8], sorted(fn)[:12])
        if d >= depth:
            dn[:] = []

print('===== robust_kbench_data =====')
tree('/root/robust_kbench_data')

print()
print('===== KernelBenchX_hf / _data =====')
tree('/root/KernelBenchX_hf')
tree('/root/KernelBenchX_data')

print()
print('===== kernel-reward-audit top =====')
tree('/root/kernel-reward-audit', 1)

print()
print('===== control_robustkbench results =====')
p = '/root/kernel-reward-audit/outputs/control_robustkbench/robust_kbench_data_results.json'
r = json.load(open(p))
print(type(r).__name__, 'len', len(r))
s = json.dumps(r, ensure_ascii=False)[:1500]
print(s)

print()
print('===== control_kernelbenchx results =====')
p = '/root/kernel-reward-audit/outputs/control_kernelbenchx/KernelBenchX_data_results.json'
r = json.load(open(p))
print(type(r).__name__, 'len', len(r))
print(json.dumps(r, ensure_ascii=False)[:1500])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_probe_native2.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _probe_native2.py",
      timeout=300)
c.close()
print("PROBE_DONE")
