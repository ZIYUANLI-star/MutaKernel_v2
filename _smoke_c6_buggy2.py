import _remote as R

sh = r"""
set -e
PY=/root/miniconda3/bin/python
OUT=/root/mk_v2_runs/e3_campaign/wave15/_smoke/c6
D=/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data

cd /root/mk_v2_ops
PATH=/usr/local/cuda/bin:$PATH $PY -u run_c6_campaign.py worker \
  --meta $D/gelu_triton_buggy/meta.json \
  --kernel $D/gelu_triton_buggy/kernel.py \
  --ref $D/gelu_triton/ref_fp64.py \
  --cases $OUT/cases_mfull_buggy.json \
  --row m-full --oracle corpus_unified \
  --out $OUT/gelu_buggy_mfull2.jsonl
$PY - <<'EOF'
import json
from collections import Counter
c = Counter()
for l in open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/c6/gelu_buggy_mfull2.jsonl'):
    r = json.loads(l)
    c[r['status']] += 1
print('status split:', dict(c))
EOF
echo C6_BUGGY2_OK
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2_ops/_c6_smoke3.sh", "w") as fh:
    fh.write(sh)
sftp.close()
R.run(c, "bash /root/mk_v2_ops/_c6_smoke3.sh", timeout=900)
c.close()
print("SMOKE3_DONE")
