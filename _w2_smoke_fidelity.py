import _remote as R

sh = r"""
set -e
PY=/root/miniconda3/bin/python
OUT=/root/mk_v2_runs/e3_campaign/wave15/_smoke/fidelity
mkdir -p $OUT

head -2 /root/KernelBenchX_hf/kbx_corpus/all_records.jsonl > $OUT/records2.jsonl
cd /root/mk_v2_ops
PATH=/usr/local/cuda/bin:$PATH $PY -u run_port_fidelity.py b8 \
  --records $OUT/records2.jsonl --out-dir $OUT/b8 --timeout 300
echo '=== b8 smoke done ==='

$PY - <<'EOF'
import json
reg = json.load(open('/root/robust_kbench_data/registry.json'))
one = [r for r in reg if r['id'] == 'layernorm']
json.dump(one, open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/fidelity/reg1.json', 'w'))
EOF
PATH=/usr/local/cuda/bin:$PATH $PY -u run_port_fidelity.py b7 \
  --registry $OUT/reg1.json --out-dir $OUT/b7 --timeout 1200
echo FID_SMOKE_OK
"""
c = R.connect()
sftp = c.open_sftp()
sftp.put("_ops_src/run_port_fidelity.py", "/root/mk_v2_ops/run_port_fidelity.py")
with sftp.open("/root/mk_v2_ops/_fid_smoke.sh", "w") as fh:
    fh.write(sh)
sftp.close()
R.run(c, "bash /root/mk_v2_ops/_fid_smoke.sh", timeout=1800)
c.close()
print("SMOKE_DONE")
