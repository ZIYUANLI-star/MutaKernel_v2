import _remote as R

sh = r"""
set -e
PY=/root/miniconda3/bin/python
OUT=/root/mk_v2_runs/e3_campaign/wave15/_smoke/c6
D=/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data

cd /root/mk_v2_ops
$PY - <<'EOF'
import json, sys
sys.path.insert(0, '/root/mk_v2_ops')
from run_c6_campaign import build_row_cases
meta = json.load(open('/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data/gelu_triton_buggy/meta.json'))
src = open('/root/mk_v2/external/C6_gpuemu/gpuemu-corpus/gpuemu_corpus/data/gelu_triton_buggy/kernel.py').read()
json.dump(build_row_cases('m-full', meta, src, 'gelu_triton_buggy'),
          open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/c6/cases_mfull_buggy.json', 'w'))
print('bug note:', meta.get('notes'))
EOF

PATH=/usr/local/cuda/bin:$PATH $PY -u run_c6_campaign.py worker \
  --meta $D/gelu_triton_buggy/meta.json \
  --kernel $D/gelu_triton_buggy/kernel.py \
  --ref $D/gelu_triton_buggy/ref_fp64.py \
  --cases $OUT/cases_mfull_buggy.json \
  --row m-full --oracle corpus_unified \
  --out $OUT/gelu_buggy_mfull.jsonl
echo '--- status split ---'
$PY - <<'EOF'
import json
from collections import Counter
c = Counter()
fails = []
for l in open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/c6/gelu_buggy_mfull.jsonl'):
    r = json.loads(l)
    c[r['status']] += 1
    if r['status'] == 'FAIL' and len(fails) < 3:
        fails.append((r['case']['policy'], r.get('reason')))
print(dict(c))
print('sample fails:', fails)
EOF
echo C6_BUGGY_SMOKE_OK
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2_ops/_c6_smoke2.sh", "w") as fh:
    fh.write(sh)
sftp.close()
R.run(c, "bash /root/mk_v2_ops/_c6_smoke2.sh", timeout=900)
c.close()
print("SMOKE2_DONE")
