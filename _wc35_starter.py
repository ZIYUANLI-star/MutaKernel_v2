import _remote, time
c = _remote.connect()
R = _remote.run
s = c.open_sftp()
s.put("_wc_start.py", "/root/mk_v2/_wc_start.py")
s.put("_wc_audit.py", "/root/mk_v2/_wc_audit.py")
s.close()
R(c, "rm -f /root/mk_v2_runs/e1/witness_confirmation/audit_lane*.lock "
      "/root/mk_v2_runs/e1/witness_confirmation/STAGE_DONE_*")
cmd = ("( cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u _wc_start.py "
       "> /root/mk_v2_runs/e1/witness_confirmation/starter_stdout.log 2>&1 "
       "< /dev/null & ) ; echo SPAWNED; exit 0")
R(c, cmd, timeout=30)
time.sleep(20)
R(c, "tail -10 /root/mk_v2_runs/e1/witness_confirmation/starter.log")
c.close()
