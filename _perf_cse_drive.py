#!/usr/bin/env python3
"""Local driver: upload the read-only sampler, run it remotely, dump JSON."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_perf_cse_sample_remote.py", "/tmp/_perf_cse_sample_remote.py")
sftp.close()
code, o, e = _remote.run(
    c, "/root/miniconda3/bin/python /tmp/_perf_cse_sample_remote.py",
    timeout=600, echo=False)
with open("_perf_cse_sample_out.json", "w", encoding="utf-8") as fh:
    fh.write(o)
print("exit", code, "bytes", len(o))
if e.strip():
    print("STDERR:", e[:2000])
c.close()
