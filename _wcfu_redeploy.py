"""Kill the stalled wcfu chain, redeploy the patched version, relaunch."""
import hashlib
import time
import _remote

SRC = "_wcfu_chain_src.py"
DST = "/root/mk_v2/_wcfu_chain.py"

body = open(SRC, "rb").read()
local_md5 = hashlib.md5(body).hexdigest()

c = _remote.connect()

# 1. kill the old chain by exact pid lookup (avoid pkill -f self-match issues)
code, o, e = _remote.run(
    c, "pgrep -f '[_]wcfu_chain.py'", timeout=30, echo=False)
pids = [p for p in o.split() if p.strip().isdigit()]
print("old chain pids:", pids)
for p in pids:
    _remote.run(c, "kill %s" % p, timeout=15, echo=False)
time.sleep(2)
code, o, e = _remote.run(c, "pgrep -f '[_]wcfu_chain.py' | wc -l",
                         timeout=30, echo=False)
print("alive after kill:", o.strip())

# 2. upload patched file
sftp = c.open_sftp()
with sftp.open(DST, "wb") as fh:
    fh.write(body)
sftp.close()
code, o, e = _remote.run(c, "md5sum %s" % DST, timeout=30, echo=False)
print("md5 match:", o.split()[0] == local_md5)
assert o.split()[0] == local_md5

code, o, e = _remote.run(
    c, "/root/miniconda3/bin/python -m py_compile %s && echo COMPILE_OK" % DST,
    timeout=60, echo=False)
print(o or e)
assert "COMPILE_OK" in o

# 3. remove stale lock (old process held flock; file itself persists harmlessly
#    but truncate for clean pid record) and relaunch detached
code, o, e = _remote.run(
    c,
    "cd /root/mk_v2 && nohup /root/miniconda3/bin/python -u _wcfu_chain.py "
    ">> /root/mk_v2_runs/e3_b9_calib/wcfu_chain_stdout.log 2>&1 < /dev/null & "
    "echo LAUNCHED",
    timeout=30, echo=False)
print("launch:", (o or e).strip())
time.sleep(20)
code, o, e = _remote.run(
    c, "pgrep -f '[_]wcfu_chain.py' | head -3; echo MARK; "
       "tail -n 8 /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log",
    timeout=30, echo=False)
print(o)
c.close()
print("REDEPLOY_DONE")
