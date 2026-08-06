import _remote as R

py = r"""
import json

n = ok_before = ok_after = 0
with open('/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl') as fh:
    for l in fh:
        r = json.loads(l)
        n += 1
        for side, cnt in (('before_code', 'b'), ('after_code', 'a')):
            code = r.get(side)
            if not code:
                continue
            try:
                compile(code, '<x>', 'exec')
                if side == 'before_code':
                    ok_before += 1
                else:
                    ok_after += 1
            except SyntaxError:
                pass
print('records', n, 'before compiles', ok_before, 'after compiles', ok_after)

import pyarrow.parquet as pq
for f in ('/root/KernelBenchX_hf/corpus_all.parquet',
          '/root/KernelBenchX_hf/tasks.parquet'):
    t = pq.read_table(f)
    print(f, 'rows', t.num_rows, 'cols', t.column_names)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_kbx_check.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _kbx_check.py",
      timeout=300)
c.close()
print("DONE")
