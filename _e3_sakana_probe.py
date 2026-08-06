"""Probe the parquet columns + the existing Sakana baseline harness."""
import _remote as R

py = r"""
import pyarrow.parquet as pq
t = pq.read_file if 0 else None
import pyarrow.parquet as pq
f = pq.ParquetFile('/root/mk_v2/external/C3_ai_cuda_engineer/level_1.parquet')
print('columns:', f.schema_arrow.names)
tbl = f.read_row_group(0)
row = {c: tbl.column(c)[0].as_py() for c in tbl.column_names}
for k, v in row.items():
    s = str(v).replace('\n', ' | ')
    print('%-28s %s' % (k, s[:150]))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_sakana_probe.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_sakana_probe.py",
      timeout=300)
R.run(c, "head -80 /root/mk_v2/scripts/run_sakana_baseline_all.py", timeout=60)
c.close()
print("SAKANA_PROBE_DONE")
