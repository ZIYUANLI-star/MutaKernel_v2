import _remote as R

c = R.connect()
R.run(c, "cd /root/mk_v2 && git rev-parse HEAD && echo '--- porcelain (first 10) ---' "
         "&& git status --porcelain | head -10 && git status --porcelain | wc -l",
      timeout=60)
R.run(c, "python3 - <<'EOF'\n"
         "import json\n"
         "e = json.load(open('/root/mk_v2_runs/e3_campaign/wave1_environment_v2.json'))\n"
         "print('captured git:', json.dumps(e.get('git')))\n"
         "EOF", timeout=60)
c.close()
print("GITCHECK_DONE")
