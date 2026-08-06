import _remote as R

c = R.connect()
R.run(c, "grep -rl 'wave1_manifest_input' /root/mk_v2/ --include='*.py' "
         "| grep -v __pycache__ | head", timeout=120)
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "with open('/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft_l3.jsonl') as fh:\n"
         "    for l in fh:\n"
         "        r = json.loads(l)\n"
         "        if 'L3' in r['task_key']:\n"
         "            print('task_key:', r['task_key'])\n"
         "            print('task_id:', r.get('task_id'))\n"
         "            print('extraction:', json.dumps(r.get('extraction'), ensure_ascii=False)[:800])\n"
         "            break\n"
         "EOF", timeout=60)
c.close()
print("DONE")
