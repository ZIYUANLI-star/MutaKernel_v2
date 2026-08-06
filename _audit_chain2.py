"""Audit probe 2: root-cause the lane M env-check failures."""
import _remote as R

c = R.connect()
print("### git status of MK repo")
R.run(c, "cd /root/mk_v2 && git status --porcelain && git log --oneline -3", timeout=60)
print("### runner process age")
R.run(c, "ps -o pid,etime,lstart,cmd -p 572643 2>/dev/null | cat", timeout=60)
print("### lane_m_run.log around failures (timestamps)")
R.run(c, "grep -c 'FSE experiment failed' /root/mk_v2_runs/e3_campaign/lane_m_run.log; "
         "grep -n 'runner start\\|FSE experiment failed' /root/mk_v2_runs/e3_campaign/lane_m_run.log | tail -25", timeout=60)
print("### last observation time")
R.run(c, "stat -c '%y %n' /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl", timeout=60)
print("### guard for lane M")
R.run(c, "pgrep -af guard | grep -v pgrep; ls /root/mk_v2_ops/ | grep -i guard; "
         "crontab -l 2>/dev/null", timeout=60)
print("### captured env manifest git/nvcc fields")
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json\n"
         "m=json.load(open('/root/mk_v2_runs/e3_campaign/wave1_environment_v2.json'))\n"
         "def find(d,p=''):\n"
         "    for k,v in (d.items() if isinstance(d,dict) else []):\n"
         "        kl=k.lower()\n"
         "        if any(t in kl for t in ('git','nvcc','dirty','commit')):\n"
         "            print(p+k,'=',str(v)[:120])\n"
         "        if isinstance(v,dict): find(v,p+k+'.')\n"
         "find(m)\n"
         "EOF", timeout=60)
print("### live nvcc")
R.run(c, "which nvcc; nvcc --version 2>/dev/null | tail -1; "
         "ls /usr/local/cuda/bin/nvcc 2>/dev/null", timeout=60)
c.close()
print("AUDIT2_DONE")
