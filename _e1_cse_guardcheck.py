import _remote

c = _remote.connect()
_remote.run(c, "ps -eo pid,ppid,args | grep e1_guard.sh | grep -v grep", timeout=30)
_remote.run(c, "cat /root/mk_v2_runs/e1_guard.pid", timeout=20)
_remote.run(c, "ps -eo pid,args | awk '/run_e1_cse_falsify.py --/ && !/awk/ {c++} END {print \"cse_drivers:\", c}'", timeout=30)
c.close()
print("GUARDCHECK_DONE")
