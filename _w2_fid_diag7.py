import _remote as R

py = r"""
import json, torch
import torch.nn.functional as F

rec = None
with open('/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        if r['task_id'] == 'Activation/leaky_relu.py':
            rec = r; break
code = rec['after_code']
print(code[:3000])
print('...')

ns = {'__file__': '/tmp/_cand7.py', '__name__': 'cand7'}
open('/tmp/_cand7.py', 'w').write(code)
exec(compile(code, '/tmp/_cand7.py', 'exec'), ns)
f = ns['leaky_relu']

g = torch.Generator(); g.manual_seed(42)
x = torch.randn(1024, 1024, generator=g).cuda()
y = f(x, negative_slope=0.1, inplace=False)
exp = F.leaky_relu(x, 0.1)
d = (y - exp).abs()
print('maxdiff', d.max().item(), 'frac wrong', (d > 1e-5).float().mean().item())
# pattern: which rows/cols wrong?
wrong = (d > 1e-5)
print('wrong rows frac:', wrong.any(dim=1).float().mean().item(),
      'wrong cols frac:', wrong.any(dim=0).float().mean().item())
print('first wrong idx:', wrong.nonzero()[:5].tolist())
print('y flat[1048570:]:', y.flatten()[-6:].tolist())
print('exp flat[1048570:]:', exp.flatten()[-6:].tolist())
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_fid_diag7.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
         "/root/miniconda3/bin/python -u _fid_diag7.py", timeout=600)
c.close()
print("DONE")
