import _remote
c = _remote.connect()
_remote.run(c, "pkill -9 -f _p53_control3_remote.py; pkill -9 -f _inner_one.py; sleep 1; echo killed", timeout=30)
print("=== remaining control procs (should be none) ===")
_remote.run(c, "ps -eo pid,etime,cmd | grep -E '_inner_one|control3' | grep -v grep; echo done", timeout=30)
print("=== cgroup mem now ===")
_remote.run(c, "free -g | sed -n '1,2p'", timeout=30)
c.close()
