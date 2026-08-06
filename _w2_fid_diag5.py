import _remote as R

py = r"""
import json, re, sys, torch, types
import torch.nn.functional as F

golden_file = '/root/KernelBenchX_hf/kernelbenchx/Activation/leaky_relu.py'
golden = open(golden_file, encoding='utf-8', errors='replace').read()
ref_impl, test_part = re.split(r'\n#{40,}\n', golden, maxsplit=1)
print('=== full random section of test ===')
i = test_part.find('random')
print(test_part[max(0,i-400):i+800])

_CALL_IDX = [0]
def rand_tensor(shape, dtype=torch.float32, mode='standard',
                outlier_prob=0.001, outlier_scale=50.0, low=-1.0, high=1.0,
                device='cuda', **kw):
    g = torch.Generator(); g.manual_seed(42 + _CALL_IDX[0]); _CALL_IDX[0] += 1
    if mode == 'standard':
        v = torch.randn(shape, generator=g)
    elif mode == 'outlier':
        v = torch.randn(shape, generator=g)
        mask = torch.rand(shape, generator=g) < outlier_prob
        cnt = int(mask.sum())
        if cnt:
            v[mask] = torch.randn(cnt, generator=g) * outlier_scale
    else:
        v = (high - low) * torch.rand(shape, generator=g) + low
    return v.to(device=device, dtype=dtype)

du = types.ModuleType('data_utils'); du.rand_tensor = rand_tensor
sys.modules['data_utils'] = du

rec = None
with open('/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        if r['task_id'] == 'Activation/leaky_relu.py':
            rec = r; break

def run(impl_src, tag):
    path = '/tmp/_comb5_%s.py' % tag
    src = impl_src + '\n' + test_part
    open(path, 'w').write(src)
    ns = {'__file__': path, '__name__': '__main__'}
    _CALL_IDX[0] = 0
    torch.manual_seed(42); torch.cuda.manual_seed_all(42)
    exec(compile(src, path, 'exec'), ns)
    return ns['test_results']

r_ref = run(ref_impl, 'ref')
r_cand = run(rec['after_code'], 'cand')

# recompute expected inputs with same per-call generator
_CALL_IDX[0] = 0
xs = [rand_tensor((1024, 1024)) for _ in range(6)]  # guess: 3 standard + 3 outlier? check shapes below
key = 'test_random_standard'
for i, (a, b) in enumerate(zip(r_ref[key], r_cand[key])):
    print(key, i, 'ref==F.leaky(x%d)?' % i,
          torch.allclose(a, F.leaky_relu(xs[i]), atol=0, rtol=0),
          'cand==F.leaky(x%d)?' % i,
          torch.allclose(b, F.leaky_relu(xs[i]), atol=1e-5, rtol=1e-5),
          'maxdiff ref-cand', (a - b).abs().max().item())
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_fid_diag5.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
         "/root/miniconda3/bin/python -u _fid_diag5.py", timeout=600)
c.close()
print("DONE")
