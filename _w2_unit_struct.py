import _remote as R

PY = "/root/miniconda3/bin/python"
c = R.connect()
print("### wave-1 queue unit sample")
R.run(c, PY + " - <<'EOF'\n"
         "import json\n"
         "s=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
         "k=sorted(s['units'])[0]\n"
         "print(json.dumps(s['units'][k], indent=1))\n"
         "print('top keys:', sorted(s.keys()))\n"
         "EOF", timeout=60)
print("### L3 signed record outer keys")
R.run(c, PY + " - <<'EOF'\n"
         "import json\n"
         "line=open('/root/mk_v2_runs/e2_reconcile/contracts_l3_signed_v2.jsonl').readline()\n"
         "r=json.loads(line)\n"
         "def walk(d, p=''):\n"
         "    for k,v in d.items():\n"
         "        if isinstance(v, dict) and p.count('.')<1: walk(v, p+k+'.')\n"
         "        else: print(p+k, str(v)[:80])\n"
         "walk({k:v for k,v in r.items() if k!='contract'})\n"
         "EOF", timeout=60)
print("### how run_e3_external.py plan resolves subject-id")
R.run(c, "grep -n 'subject-id\\|subject_id\\|manifest\\|SUBJECT' /root/mk_v2/scripts/run_e3_external.py | head -30", timeout=60)
c.close()
print("DONE")
