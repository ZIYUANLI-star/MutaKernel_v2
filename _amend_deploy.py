"""Deploy and run the one-shot E1 ledger amendment (CPU-only, sync)."""
import _remote

SRC = "_amend_exec_src.py"
DST = "/root/mk_v2/_amend_exec.py"

c = _remote.connect()

# guard: refuse double application
_, o, _ = _remote.run(c, (
    "ls /root/mk_v2_runs/e1/amendment_v1/amendment_manifest.json 2>/dev/null; "
    "echo GUARD_END"), timeout=30, echo=False)
if "amendment_manifest.json" in o:
    raise SystemExit("BLOCKED: amendment already applied:\n" + o)

sftp = c.open_sftp()
sftp.put(SRC, DST)
sftp.close()

_, o, e = _remote.run(c, "/root/miniconda3/bin/python -m py_compile %s && echo COMPILE_OK" % DST,
                      timeout=60, echo=False)
if "COMPILE_OK" not in o:
    raise SystemExit("compile failed: %s %s" % (o, e))

_, o, e = _remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _amend_exec.py",
                      timeout=300, echo=False)
print(o)
if e.strip():
    print("STDERR:\n" + e)
c.close()
