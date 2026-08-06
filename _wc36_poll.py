import _remote
c = _remote.connect()
R = _remote.run
O = "/root/mk_v2_runs/e1/witness_confirmation"
R(c, "echo '--- lane0:'; tail -3 %s/audit_lane0.log; "
      "echo '--- lane1:'; tail -3 %s/audit_lane1.log; "
      "echo '--- starter:'; tail -2 %s/starter.log; "
      "echo '--- cells:'; ls %s/cells/ctrl__*__*__*.json 2>/dev/null | wc -l; "
      "ls %s/cells/conf__*.json 2>/dev/null | wc -l; "
      "echo '--- diverged control cells:'; grep -l '\"status\": \"fail\"' %s/cells/ctrl__*.json 2>/dev/null; "
      "echo '--- oom/mem/gpu:'; grep oom_kill /sys/fs/cgroup/memory/memory.oom_control; "
      "free -g | sed -n 2p; nvidia-smi --query-gpu=memory.used --format=csv,noheader; "
      "ls /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN >/dev/null 2>&1 && echo 'brake: HELD' || echo 'brake: LIFTED'; date"
      % (O, O, O, O, O, O))
c.close()
