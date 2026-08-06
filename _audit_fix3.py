"""Fix 3: redeploy patched wave2 orchestrator and restart it."""
import time
import _remote as R

c = R.connect()
sftp = c.open_sftp()
sftp.put("_ops_src/wave2_orchestrator.py", "/root/mk_v2_ops/wave2_orchestrator.py")
sftp.close()
R.run(c, "/root/miniconda3/bin/python -m py_compile /root/mk_v2_ops/wave2_orchestrator.py && echo COMPILE_OK",
      timeout=120)
R.run(c, "kill 317453 2>/dev/null; sleep 2; pgrep -af wave2_orchestrator || echo old_gone",
      timeout=60)
R.run(c, "rm -f /root/mk_v2_runs/e3_campaign/wave2/orchestrator.pid; "
         "cd /root/mk_v2_ops && "
         "(setsid nohup /root/miniconda3/bin/python -u wave2_orchestrator.py "
         "> /root/mk_v2_runs/e3_campaign/wave2/orchestrator_nohup.log 2>&1 < /dev/null &) ; "
         "echo spawned", timeout=30)
time.sleep(4)
R.run(c, "pgrep -af wave2_orchestrator; "
         "tail -3 /root/mk_v2_runs/e3_campaign/wave2/orchestrator.log", timeout=60)
c.close()
print("FIX3_DONE")
