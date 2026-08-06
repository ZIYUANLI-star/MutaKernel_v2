import _remote as R

py = r"""
import json, re, sys, torch, types, os

golden_file = '/root/KernelBenchX_hf/kernelbenchx/Activation/leaky_relu.py'
golden = open(golden_file, encoding='utf-8', errors='replace').read()
parts = re.split(r'\n#{40,}\n', golden, maxsplit=1)
ref_impl, test_part = parts
print('impl head:', ref_impl[:200])
print('test part head:', test_part[:400])

def rand_tensor(shape, dtype=torch.float32, mode='standard',
                outlier_prob=0.001, outlier_scale=50.0, low=-1.0, high=1.0,
                device='cuda', **kw):
    if mode == 'standard':
        v = torch.randn(shape)
    elif mode == 'outlier':
        v = torch.randn(shape)
        mask = torch.rand(shape) < outlier_prob
        cnt = int(mask.sum())
        if cnt:
            v[mask] = torch.randn(cnt) * outlier_scale
    else:
        v = (high - low) * torch.rand(shape) + low
    return v.to(device=device, dtype=dtype)

du = types.ModuleType('data_utils')
du.rand_tensor = rand_tensor
sys.modules['data_utils'] = du

def run(impl_src, tag):
    path = '/tmp/_comb_%s.py' % tag
    src = impl_src + '\n' + test_part
    open(path, 'w').write(src)
    ns = {'__file__': path, '__name__': '__main__'}
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    exec(compile(src, path, 'exec'), ns)
    return ns['test_results']

r1 = run(ref_impl, 'a')
r2 = run(ref_impl, 'b')
for k in r1:
    v1, v2 = r1[k], r2[k]
    if isinstance(v1, list):
        same = all(torch.equal(a, b) for a, b in zip(v1, v2))
    else:
        same = torch.equal(v1, v2)
    print(k, 'identical:', same)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_fid_diag3.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
         "/root/miniconda3/bin/python -u _fid_diag3.py", timeout=600)
c.close()
print("DONE")
