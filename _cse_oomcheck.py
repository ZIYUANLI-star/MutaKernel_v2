import _remote

c = _remote.connect()
_remote.run(c, "cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null; "
               "cat /sys/fs/cgroup/memory/memory.failcnt 2>/dev/null; "
               "cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null; "
               "free -g | head -2", timeout=30)
c.close()
print("OOMCHECK_DONE")
