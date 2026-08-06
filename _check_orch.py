import _remote as R

c = R.connect()
R.run(c, "ps aux | grep wave15_orchestrator | grep -v grep; echo ---; "
         "cat /root/mk_v2_runs/e3_campaign/wave15/orchestrator.pid 2>/dev/null; echo ---; "
         "tail -10 /root/mk_v2_runs/e3_campaign/wave15/orchestrator.log 2>/dev/null",
      timeout=60)
c.close()
print("DONE")
