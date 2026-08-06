import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "e = json.load(open('/root/mk_v2_runs/e3_campaign/wave1_environment_v2.json'))\n"
         "print('captured git:', json.dumps(e.get('git')))\n"
         "EOF", timeout=60)
c.close()
print("DONE")
