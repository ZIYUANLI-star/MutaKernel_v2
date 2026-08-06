import time
import _remote

SRC = "_s2_chain_src.py"
DST = "/root/mk_v2/_s2_chain.py"

c = _remote.connect()
_, o, _ = _remote.run(c, "pgrep -af '[_]s2_chain.py' || echo NONE", timeout=30, echo=False)
if "NONE" not in o:
    raise SystemExit("s2 chain already running: %s" % o)

sftp = c.open_sftp()
sftp.put(SRC, DST)
sftp.close()

_, o, e = _remote.run(c, "/root/miniconda3/bin/python -m py_compile %s && echo COMPILE_OK" % DST,
                      timeout=60, echo=False)
if "COMPILE_OK" not in o:
    raise SystemExit("compile failed: %s %s" % (o, e))
print("compiled OK")

try:
    _remote.run(c, (
        "cd /root/mk_v2 && nohup /root/miniconda3/bin/python -u _s2_chain.py "
        ">> /root/mk_v2_runs/e3_b9_calib/s2_chain_stdout.log 2>&1 < /dev/null & "
        "echo PID=$!"), timeout=15, echo=False)
except Exception as exc:
    print("launch channel timeout (expected): %r" % exc)

time.sleep(6)
c2 = _remote.connect()
_, o, _ = _remote.run(c2, (
    "pgrep -af '[_]s2_chain.py'; echo ---; "
    "tail -3 /root/mk_v2_runs/e3_b9_calib/s2_chain.log 2>/dev/null"),
    timeout=30, echo=False)
print(o)
c2.close()
print("S2_CHAIN_DEPLOY_DONE")
