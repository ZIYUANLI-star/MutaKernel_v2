import _remote

c = _remote.connect()
_remote.run(c, (
    "echo '--- b9 procs remaining ---'; "
    "ps aux | grep -E 'guard_b9|_b9_calib_driver|e3_b9_calib' | grep -v grep; "
    "echo '--- count ---'; "
    "ps aux | grep -E 'guard_b9|_b9_calib_driver|e3_b9_calib' | grep -v grep | wc -l; "
    "echo '--- cse worker ---'; ps aux | grep '_mutant_[w]orker' | awk '{print $2,$3,$4}'; "
    "echo '--- cse driver ---'; ps aux | grep 'signoff_[r]equeue' | grep -v bash | awk '{print $2}'; "
    "echo '--- gpu ---'; nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
    "echo '--- oom ---'; grep oom_kill /sys/fs/cgroup/memory.events; "
    "echo '--- b9 completed counts ---'; "
    "wc -l /root/mk_v2_runs/e3_b9_calib/calibration_lane*.jsonl; "
    "echo '--- pause marker ---'; ls -la /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN"
), timeout=120)
c.close()
