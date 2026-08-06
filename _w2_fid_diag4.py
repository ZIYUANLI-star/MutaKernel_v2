import _remote as R

py = r"""
import json, re, sys, torch, types

golden_file = '/root/KernelBenchX_hf/kernelbenchx/Activation/leaky_relu.py'
golden = open(golden_file, encoding='utf-8', errors='replace').read()
ref_impl, test_part = re.split(r'\n#{40,}\n', golden, maxsplit=1)

rec = None
with open('/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        if r['task_id'] == 'Activation/leaky_relu.py':
            rec = r
            break
cand_impl = rec['after_code']
print('cand head:', cand_impl[:300])

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
    path = '/tmp/_comb4_%s.py' % tag
    src = impl_src + '\n' + test_part
    open(path, 'w').write(src)
    ns = {'__file__': path, '__name__': '__main__'}
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    exec(compile(src, path, 'exec'), ns)
    return ns['test_results']

r_ref = run(ref_impl, 'ref')
r_cand = run(cand_impl, 'cand')
for k in r_ref:
    v1, v2 = r_ref[k], r_cand.get(k)
    def fl(v):
        return v if isinstance(v, list) else [v]
    for i, (a, b) in enumerate(zip(fl(v1), fl(v2))):
        d = (a.float() - b.float()).abs().max().item()
        print(k, i, 'shape', tuple(a.shape), 'maxdiff', d,
              'a[:3]', a.flatten()[:3].tolist(),
              'b[:3]', b.flatten()[:3].tolist())
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_fid_diag4.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
         "/root/miniconda3/bin/python -u _fid_diag4.py", timeout=600)
c.close()
print("DONE")
