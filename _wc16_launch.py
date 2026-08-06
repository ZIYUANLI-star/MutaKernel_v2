import _remote, time
c = _remote.connect()
R = _remote.run
cmd = ("cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u _wc_audit.py run "
       "--stage control --n-a 50 --n-b 20 "
       "> /root/mk_v2_runs/e1/witness_confirmation/control_stdout.log 2>&1 "
       "< /dev/null & echo SPAWNED; exit 0")
R(c, "mkdir -p /root/mk_v2_runs/e1/witness_confirmation")
R(c, cmd, timeout=60)
time.sleep(45)
R(c, "tail -20 /root/mk_v2_runs/e1/witness_confirmation/control_stdout.log; ls /root/mk_v2_runs/e1/witness_confirmation/cells 2>/dev/null | wc -l")
c.close()
