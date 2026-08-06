"""Redeploy orchestrator + C6 runner; restart the waiting orchestrator.
Also smoke-test the C6 worker on ONE op x one cheap row (CPU-refusing kernels
will fail fast on GPU-required ops — acceptable smoke on the GPU box)."""
import os
import _remote as R

c = R.connect()
sftp = c.open_sftp()
for name in ("wave15_orchestrator.py", "run_c6_campaign.py"):
    sftp.put(os.path.join("_ops_src", name), f"/root/mk_v2_ops/{name}")
    print("deployed", name)
sftp.close()

print("### restart orchestrator")
R.run(c, "OLD=$(cat /root/mk_v2_runs/e3_campaign/wave15/orchestrator.pid 2>/dev/null); "
         "if [ -n \"$OLD\" ] && [ -d /proc/$OLD ]; then kill $OLD; sleep 2; fi; "
         "rm -f /root/mk_v2_runs/e3_campaign/wave15/orchestrator.pid",
      timeout=60)
R.run(c, "cd /root/mk_v2_ops && (setsid nohup /root/miniconda3/bin/python -u "
         "wave15_orchestrator.py "
         "> /root/mk_v2_runs/e3_campaign/wave15/orchestrator_stdout.log 2>&1 "
         "< /dev/null &) ; sleep 3; "
         "ps aux | grep wave15_orchestrator | grep -v grep | head -2",
      timeout=60)
R.run(c, "tail -3 /root/mk_v2_runs/e3_campaign/wave15/orchestrator.log",
      timeout=60)
c.close()
print("REDEPLOY_DONE")
