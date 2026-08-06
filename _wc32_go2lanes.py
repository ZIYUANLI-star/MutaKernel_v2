import _remote, time
c = _remote.connect()
R = _remote.run
for lane in (0, 1):
    cmd = ("( cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u _wc_audit.py run "
           "--stage all --n-a 10 --n-b 20 --lane %d --lanes 2 "
           "> /root/mk_v2_runs/e1/witness_confirmation/lane%d_stdout.log 2>&1 "
           "< /dev/null & ) ; echo SPAWNED_%d; exit 0" % (lane, lane, lane))
    R(c, cmd, timeout=30)
time.sleep(30)
R(c, "tail -4 /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log; echo ---; "
      "tail -4 /root/mk_v2_runs/e1/witness_confirmation/audit_lane1.log; echo ---; "
      "ls /root/mk_v2_runs/e1/witness_confirmation/cells/*.json | wc -l; "
      "nvidia-smi --query-gpu=memory.used --format=csv,noheader; free -g | sed -n 2p")
c.close()
