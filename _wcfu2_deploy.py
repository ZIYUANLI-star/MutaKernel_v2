"""Deploy and launch _wcfu2_chain.py."""
import hashlib
import time
import _remote

SRC = "_wcfu2_chain_src.py"
DST = "/root/mk_v2/_wcfu2_chain.py"

body = open(SRC, "rb").read()
local_md5 = hashlib.md5(body).hexdigest()

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open(DST, "wb") as fh:
    fh.write(body)
sftp.close()
code, o, e = _remote.run(c, "md5sum %s" % DST, timeout=30, echo=False)
assert o.split()[0] == local_md5, "upload corrupted"
code, o, e = _remote.run(
    c, "/root/miniconda3/bin/python -m py_compile %s && echo COMPILE_OK" % DST,
    timeout=60, echo=False)
assert "COMPILE_OK" in o, "py_compile failed: %s" % (e or o)
print("uploaded + compiled ok")

try:
    _remote.run(
        c,
        "cd /root/mk_v2 && nohup /root/miniconda3/bin/python -u _wcfu2_chain.py "
        ">> /root/mk_v2_runs/e3_b9_calib/wcfu2_chain_stdout.log 2>&1 "
        "< /dev/null & echo LAUNCHED",
        timeout=10, echo=False)
except Exception as exc:
    print("launch channel note:", type(exc).__name__)

time.sleep(5)
code, o, e = _remote.run(
    c, "pgrep -f '[_]wcfu2_chain.py' | head -3; echo MARK; "
       "tail -n 4 /root/mk_v2_runs/e3_b9_calib/wcfu2_chain.log 2>/dev/null",
    timeout=30, echo=False)
print(o)
c.close()
print("WCFU2_DEPLOY_DONE")
