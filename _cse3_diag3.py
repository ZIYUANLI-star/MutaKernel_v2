#!/usr/bin/env python3
import _remote

c = _remote.connect()
_remote.run(c, "ls /root/mk_v2/KernelBench | head -20", timeout=60)
_remote.run(c, "find /root/mk_v2/KernelBench -maxdepth 2 -type d | head -20",
            timeout=60)
_remote.run(c, "grep -n 'def _resolve_problem_file' -A 12 "
               "/root/mk_v2/scripts/run_e1_probe_study.py", timeout=60)
c.close()
