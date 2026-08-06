#!/usr/bin/env python3
"""Local driver: run the CPU microbenchmark remotely under nice."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_perf_cse_bench_remote.py", "/tmp/_perf_cse_bench_remote.py")
sftp.close()
code, o, e = _remote.run(
    c, "nice -n 15 /root/miniconda3/bin/python /tmp/_perf_cse_bench_remote.py",
    timeout=900, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:2000])
print("exit", code)
c.close()
