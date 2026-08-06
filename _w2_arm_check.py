import _remote as R

c = R.connect()
R.run(c, "pgrep -af 'wave2_orchestrator|wave15_orchestrator'", timeout=60)
R.run(c, "cat /root/mk_v2_runs/e3_campaign/wave2/orchestrator.pid 2>/dev/null; echo ---; "
         "tail -10 /root/mk_v2_runs/e3_campaign/wave2/orchestrator.log 2>/dev/null; echo ---; "
         "ls /root/mk_v2_runs/e3_campaign/wave15/ 2>/dev/null | head", timeout=60)
c.close()
print("DONE")
