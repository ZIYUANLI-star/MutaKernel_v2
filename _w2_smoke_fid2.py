import _remote as R

sh = r"""
set -e
PY=/root/miniconda3/bin/python
OUT=/root/mk_v2_runs/e3_campaign/wave15/_smoke/fidelity
rm -rf $OUT/b7 $OUT/b8
head -3 /root/KernelBenchX_hf/kbx_corpus/all_records.jsonl > $OUT/records3.jsonl

cd /root/mk_v2_ops
PATH=/usr/local/cuda/bin:$PATH $PY -u run_port_fidelity.py b8 \
  --records $OUT/records3.jsonl --out-dir $OUT/b8 --timeout 300
echo '=== b8 smoke2 done ==='
PATH=/usr/local/cuda/bin:$PATH $PY -u run_port_fidelity.py b7 \
  --registry $OUT/reg1.json --out-dir $OUT/b7 --timeout 1200
echo FID_SMOKE2_OK
"""
c = R.connect()
sftp = c.open_sftp()
sftp.put("_ops_src/run_port_fidelity.py", "/root/mk_v2_ops/run_port_fidelity.py")
with sftp.open("/root/mk_v2_ops/_fid_smoke2.sh", "w") as fh:
    fh.write(sh)
sftp.close()
R.run(c, "bash /root/mk_v2_ops/_fid_smoke2.sh", timeout=2400)
c.close()
print("SMOKE_DONE")
