import os
import _remote as R

c = R.connect()
sftp = c.open_sftp()
sftp.get("/root/robust_kbench_data/problems/problem_layernorm.py",
         "_remote_src/problem_layernorm.py")
print("fetched problem_layernorm.py",
      os.path.getsize("_remote_src/problem_layernorm.py"))
sftp.close()

R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "reg = json.load(open('/root/robust_kbench_data/registry.json'))\n"
         "print('registry entries:', len(reg))\n"
         "for r in reg:\n"
         "    print(' ', r['id'], '| keys:', sorted(r.keys()))\n"
         "print()\n"
         "import csv\n"
         "with open('/root/robust_kbench_data/highlighted/results.csv') as fh:\n"
         "    rd = csv.DictReader(fh)\n"
         "    for row in rd:\n"
         "        print(row.get('task_name'), '| Correct=', row.get('Correct'),\n"
         "              '| forward=', row.get('forward'))\n"
         "EOF", timeout=120)

R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, ast\n"
         "with open('/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl') as fh:\n"
         "    r = json.loads(fh.readline())\n"
         "before = ast.literal_eval(r['before'])\n"
         "after = ast.literal_eval(r['after'])\n"
         "print('before:', {k: before[k] for k in ('call_ok','exe_ok','perf_ok','dtype')})\n"
         "print('after:', {k: after[k] for k in ('call_ok','exe_ok','perf_ok','dtype')})\n"
         "print('before_code len:', len(r['before_code']), 'after_code len:', len(r['after_code']))\n"
         "print('task_id:', r['task_id'])\n"
         "from collections import Counter\n"
         "c1 = Counter(); c2 = Counter(); tasks = set()\n"
         "n = 0\n"
         "with open('/root/KernelBenchX_hf/kbx_corpus/all_records.jsonl') as fh:\n"
         "    for l in fh:\n"
         "        r = json.loads(l)\n"
         "        n += 1\n"
         "        tasks.add(r['task_id'])\n"
         "        b = ast.literal_eval(r['before']); a = ast.literal_eval(r['after'])\n"
         "        c1[(bool(r['before_code_present']=='True' or r['before_code_present'] is True), b.get('exe_ok'))] += 1\n"
         "        c2[(bool(r['after_code_present']=='True' or r['after_code_present'] is True), a.get('exe_ok'))] += 1\n"
         "print('records', n, 'distinct tasks', len(tasks))\n"
         "print('before (code_present, exe_ok):', dict(c1))\n"
         "print('after  (code_present, exe_ok):', dict(c2))\n"
         "EOF", timeout=120)
c.close()
print("DONE")
