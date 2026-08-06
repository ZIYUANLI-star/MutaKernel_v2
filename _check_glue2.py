import _remote as R

c = R.connect()
print("### where is the guard script + its completion logic")
R.run(c, "ps aux | grep -i guard | grep -v grep; "
         "ls /root/mk_v2/*.sh /root/*.sh 2>/dev/null | head", timeout=60)
print("### completion strings in the live guard")
R.run(c, "GS=$(ps aux | grep 'bash.*guard' | grep -v grep | awk '{for(i=11;i<=NF;i++) if ($i ~ /guard/) print $i}' | head -1); "
         "echo GUARD=$GS; grep -n 'DONE\\|COMPLETE\\|while\\|exit' $GS 2>/dev/null | head -25", timeout=60)
print("### which matrix file matches lane M plan v2")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, glob, hashlib\n"
         "plan = json.load(open('/root/mk_v2_runs/e3_campaign/wave1_lane_m_plan_v2.json'))\n"
         "want = plan['strategy_matrix_file_sha256']\n"
         "print('want file sha:', want)\n"
         "for f in glob.glob('/root/mk_v2/configs/*.json') + glob.glob('/root/mk_v2_runs/e3_campaign/*.json'):\n"
         "    h = hashlib.sha256(open(f,'rb').read()).hexdigest()\n"
         "    if h == want:\n"
         "        print('MATCH:', f)\n"
         "print('scope:', plan['experiment_scope'])\n"
         "print('configs:', glob.glob('/root/mk_v2/configs/*.json'))\n"
         "EOF", timeout=120)
c.close()
print("DONE")
