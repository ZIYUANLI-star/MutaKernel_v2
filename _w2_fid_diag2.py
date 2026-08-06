import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "for l in open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/fidelity/b8/b8_fidelity.jsonl'):\n"
         "    r = json.loads(l)\n"
         "    if r.get('skipped'):\n"
         "        print(r['task_id'], r['side'], 'SKIP', r['skipped']); continue\n"
         "    print(r['task_id'], r['side'], '| call', r.get('replicated_call_ok'),\n"
         "          '| exe', r.get('replicated_exe_ok'))\n"
         "    print('   err:', str(r.get('error'))[:300])\n"
         "    print('   mm:', r.get('mismatch'))\n"
         "EOF", timeout=60)
c.close()
print("DONE")
