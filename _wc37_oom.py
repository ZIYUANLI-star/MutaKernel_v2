import _remote
c = _remote.connect()
R = _remote.run
R(c, "cat /proc/self/cgroup; echo ---; "
      "for f in /sys/fs/cgroup/memory/memory.oom_control /sys/fs/cgroup/memory.events "
      "/sys/fs/cgroup/memory/memory.failcnt; do echo \"== $f\"; cat $f 2>&1 | head -5; done; "
      "echo ---; dmesg 2>/dev/null | grep -ci 'killed process' || echo 'dmesg unavailable'")
c.close()
