"""Redeploy both orchestrators with lane prewarm; restart the idle waiters."""
import time
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()
sftp = c.open_sftp()
sftp.put("_ops_src/wave15_orchestrator.py", "/root/mk_v2_ops/wave15_orchestrator.py")
sftp.put("_ops_src/wave2_orchestrator.py", "/root/mk_v2_ops/wave2_orchestrator.py")
sftp.close()
R.run(c, "/root/miniconda3/bin/python -m py_compile /root/mk_v2_ops/wave15_orchestrator.py "
         "/root/mk_v2_ops/wave2_orchestrator.py && echo COMPILE_OK", timeout=120)

print("### restart wave15 orchestrator (idle: waiting LANE_M_DONE)")
R.run(c, "kill 262178 2>/dev/null; sleep 2; "
         f"rm -f {OUT}/wave15/orchestrator.pid; "
         "cd /root/mk_v2_ops && (setsid nohup /root/miniconda3/bin/python -u "
         f"wave15_orchestrator.py > {OUT}/wave15/orchestrator_stdout.log 2>&1 &); "
         "sleep 3; pgrep -af wave15_orchestrator | grep -v grep", timeout=60)

print("### restart wave2 orchestrator (idle: waiting CHAIN_DONE)")
R.run(c, "kill 328254 2>/dev/null; sleep 2; "
         f"rm -f {OUT}/wave2/orchestrator.pid; "
         "cd /root/mk_v2_ops && (setsid nohup /root/miniconda3/bin/python -u "
         f"wave2_orchestrator.py > {OUT}/wave2/orchestrator_nohup.log 2>&1 &); "
         "sleep 3; pgrep -af wave2_orchestrator | grep -v grep", timeout=60)

print("### prewarm progress")
R.run(c, f"tail -3 {OUT}/prewarm_run.log; "
         f"grep -c '\"status\": \"ok\"' {OUT}/lane_m_run/prewarm_log.jsonl 2>/dev/null; "
         f"ls {OUT}/lane_m_run/torch_extensions/ | wc -l; uptime", timeout=60)
c.close()
print("WIRE_DONE")
