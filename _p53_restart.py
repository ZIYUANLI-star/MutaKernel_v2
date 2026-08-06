import _remote
c = _remote.connect()
print("=== BEFORE: pids ===")
_remote.run(c, "pgrep -f 'run_e1_cse_falsify.py.*--lane 3$'; echo ---worker---; pgrep -f '_mutant_worker.*const_perturb__4'; echo ---guard---; cat /root/mk_v2_runs/e1_guard.pid", timeout=30)
print("=== KILL driver 89920 + its P53 worker (guard 91971 untouched) ===")
# kill the lane-3 driver and its current worker child; guard will AUTORESTART with new code
_remote.run(c, "pkill -9 -f 'run_e1_cse_falsify.py.*--lane 3$'; pkill -9 -f '_mutant_worker.*const_perturb__4'; sleep 2; echo killed", timeout=30)
print("=== AFTER kill: lane3 driver should be gone; guard alive ===")
_remote.run(c, "pgrep -af 'run_e1_cse_falsify.py.*--lane 3$'; echo ---; pgrep -af e1_guard_cse_split; echo ---lane4 still up---; pgrep -af 'run_e1_cse_falsify.py.*--lane 4$'", timeout=30)
c.close()
