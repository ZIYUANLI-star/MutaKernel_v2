# -*- coding: utf-8 -*-
"""散落数字核验:C1 构成(90 内核/16 算子)、环境版本、E0/E1 协议常量。只读。"""
import _remote

SCRIPT = r'''
import json, collections

def load_obs(p):
    return [json.loads(l) for l in open(p) if l.strip()]

b = load_obs('/root/mk_v2_runs/e1/baseline_observations.jsonl')
kernels = set(o['kernel'] for o in b)
ops = set(o['operator_name'] for o in b)
lv = collections.Counter(k.split('_')[0] for k in kernels)
print('C1: unique kernels =', len(kernels), 'by level:', dict(lv))
print('C1: unique operators =', len(ops))
print('operators:', sorted(ops))
# <=3 per kernel-operator pair
pair = collections.Counter((o['kernel'], o['operator_name']) for o in b)
print('max probes per kernel-operator pair:', max(pair.values()), '| pairs:', len(pair))

print()
m = json.load(open('/root/mk_v2_runs/e1/baseline_run_manifest.json'))
print('baseline manifest snippet:', json.dumps(m)[:1200])
print()
m0 = json.load(open('/root/mk_v2_runs/e0_run5_s0/run_manifest.json'))
print('e0 run5 manifest snippet:', json.dumps(m0)[:1200])
'''

c = _remote.connect()
_remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300)
print('### environment versions')
_remote.run(c, "/root/miniconda3/bin/python -c \"import torch, triton; print('torch', torch.__version__, '| cuda', torch.version.cuda, '| triton', triton.__version__)\"", timeout=120)
_remote.run(c, "compute-sanitizer --version 2>/dev/null || /usr/local/cuda/bin/compute-sanitizer --version", timeout=60)
_remote.run(c, "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -2", timeout=60)
c.close()
