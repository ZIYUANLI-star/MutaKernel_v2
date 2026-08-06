import _remote as R

sh = r"""
set -e
PY=/root/miniconda3/bin/python
OUT=/root/mk_v2_runs/e3_campaign/wave15/_smoke/c6
mkdir -p $OUT
D=/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data

cd /root/mk_v2_ops
$PY - <<'EOF'
import json, sys
sys.path.insert(0, '/root/mk_v2_ops')
from run_c6_campaign import build_row_cases
meta = json.load(open('/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data/gelu_triton/meta.json'))
src = open('/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data/gelu_triton/kernel.py').read()
for row in ('b1u', 'm-full', 'm-dir', 'b9-port'):
    cases = build_row_cases(row, meta, src, 'gelu_triton')
    cost = sum(c['cost'] for c in cases)
    print(row, 'cases', len(cases), 'cost', cost)
json.dump(build_row_cases('b1u', meta, src, 'gelu_triton'),
          open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/c6/cases_b1u.json', 'w'))
EOF

PATH=/usr/local/cuda/bin:$PATH $PY -u run_c6_campaign.py worker \
  --meta $D/gelu_triton/meta.json \
  --kernel $D/gelu_triton/kernel.py \
  --ref $D/gelu_triton/ref_fp64.py \
  --cases $OUT/cases_b1u.json \
  --row b1u --oracle corpus_unified \
  --out $OUT/gelu_b1u.jsonl
echo '--- observations ---'
cat $OUT/gelu_b1u.jsonl
echo C6_SMOKE_OK
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2_ops/_c6_smoke.sh", "w") as fh:
    fh.write(sh)
sftp.close()
R.run(c, "bash /root/mk_v2_ops/_c6_smoke.sh", timeout=900)
c.close()
print("SMOKE_DONE")
