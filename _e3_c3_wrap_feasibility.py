"""Feasibility: nvcc availability + functional-adapter convention across C3."""
import _remote as R

py = r"""
import json, re
import pyarrow.parquet as pq

# which (level, task) pairs are wave-1 C3 subjects?
reg = json.load(open('/root/mk_v2_runs/e3_corpora/c3_wave1/registry.json'))
want = {}
for s in reg['subjects']:
    tk = s['task_key']            # KB_L1_P1
    lvl = int(tk.split('_')[1][1:])
    pid = int(tk.split('_')[2][1:])
    want[(lvl, pid)] = s['stable_id']
print('wave-1 C3 subjects:', len(want))

import hashlib
def norm(src):
    lines = [l.rstrip() for l in src.replace('\r\n', '\n').split('\n')]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines) + '\n'

found, fn_ok, fn_bad, missing_func = 0, 0, [], []
for lvl in (1, 2):
    t = pq.read_table('/root/mk_v2/external/C3_ai_cuda_engineer/level_%d.parquet' % lvl)
    d = t.to_pylist()
    for row in d:
        key = (int(row['Level_ID']), int(row['Task_ID']))
        sid = want.get(key)
        if sid is None or not row.get('CUDA_Code'):
            continue
        h = hashlib.sha256(norm(row['CUDA_Code']).encode()).hexdigest()
        if h != sid:
            continue   # not the representative kernel for this task
        found += 1
        func = row.get('PyTorch_Code_Functional')
        if not func or not func.strip():
            missing_func.append(row['Op_Name'])
            continue
        if re.search(r'fn\s*=\s*module_fn', func) and 'def module_fn' in func:
            fn_ok += 1
        else:
            fn_bad.append(row['Op_Name'])
print('representative rows matched:', found)
print('functional fn=module_fn convention OK:', fn_ok)
print('missing functional:', missing_func[:5], 'count', len(missing_func))
print('non-standard functional:', fn_bad[:5], 'count', len(fn_bad))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_c3feas.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "which nvcc; ls /usr/local/cuda*/bin/nvcc 2>/dev/null; "
         "ls /root/miniconda3/bin/nvcc 2>/dev/null; echo ---", timeout=60)
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_c3feas.py",
      timeout=900)
c.close()
print("FEAS_DONE")
