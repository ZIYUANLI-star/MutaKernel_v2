"""Deploy wave-2 ops scripts and arm the wave-2 orchestrator behind wave-1.5."""
import _remote as R

FILES = [
    ("_ops_src/wave2_prep.py", "/root/mk_v2_ops/wave2_prep.py"),
    ("_ops_src/run_port_fidelity.py", "/root/mk_v2_ops/run_port_fidelity.py"),
    ("_ops_src/offline_close_analysis.py",
     "/root/mk_v2_ops/offline_close_analysis.py"),
    ("_ops_src/wave2_orchestrator.py", "/root/mk_v2_ops/wave2_orchestrator.py"),
]

c = R.connect()
sftp = c.open_sftp()
for local, remote in FILES:
    sftp.put(local, remote)
    print("uploaded", remote)
sftp.close()

print("### syntax check")
for _, remote in FILES:
    R.run(c, f"/root/miniconda3/bin/python -m py_compile {remote} && echo OK {remote}",
          timeout=120)

print("### existing cron guards")
R.run(c, "crontab -l 2>/dev/null | tail -20", timeout=60)

print("### arm wave-2 orchestrator (waits for wave-1.5 CHAIN_DONE)")
R.run(c, "mkdir -p /root/mk_v2_runs/e3_campaign/wave2 && "
         "cd /root/mk_v2_ops && "
         "setsid nohup /root/miniconda3/bin/python -u wave2_orchestrator.py "
         "> /root/mk_v2_runs/e3_campaign/wave2/orchestrator_nohup.log 2>&1 < /dev/null & "
         "sleep 2; echo spawned", timeout=30)
R.run(c, "sleep 3; pgrep -af wave2_orchestrator | grep -v grep; "
         "cat /root/mk_v2_runs/e3_campaign/wave2/orchestrator.pid 2>/dev/null; "
         "tail -5 /root/mk_v2_runs/e3_campaign/wave2/orchestrator.log 2>/dev/null",
      timeout=60)
c.close()
print("DONE")
