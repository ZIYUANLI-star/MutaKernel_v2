"""Deploy _wcfu_chain.py to the A800 and launch it detached."""
import hashlib
import _remote

SRC = "_wcfu_chain_src.py"
DST = "/root/mk_v2/_wcfu_chain.py"

body = open(SRC, "rb").read()
local_md5 = hashlib.md5(body).hexdigest()

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open(DST, "wb") as fh:
    fh.write(body)
sftp.close()

code, o, e = _remote.run(c, "md5sum %s" % DST, timeout=30, echo=False)
remote_md5 = o.split()[0] if o else "?"
print("md5 local=%s remote=%s match=%s" % (local_md5, remote_md5,
                                           local_md5 == remote_md5))
assert local_md5 == remote_md5, "upload corrupted"

code, o, e = _remote.run(
    c, "/root/miniconda3/bin/python -m py_compile %s && echo COMPILE_OK" % DST,
    timeout=60, echo=False)
print(o or e)
assert "COMPILE_OK" in o, "py_compile failed: %s" % e

code, o, e = _remote.run(
    c,
    "cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u _wcfu_chain.py "
    ">> /root/mk_v2_runs/e3_b9_calib/wcfu_chain_stdout.log 2>&1 < /dev/null & "
    "sleep 3; pgrep -f _wcfu_chain.py | head -3; "
    "tail -n 5 /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log 2>/dev/null",
    timeout=30, echo=False)
print("launch:", o or e)
c.close()
print("DEPLOY_DONE")
