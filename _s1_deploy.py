"""Deploy the aggregation script and the stage-1 chainer, then launch the chainer."""
import sys
from pathlib import Path

import _remote

FILES = {
    "_b9_aggregate.py": "/root/mk_v2/_b9_aggregate.py",
    "_b9_stage1_chain.py": "/root/mk_v2/_b9_stage1_chain.py",
}
LAUNCH = (
    "cd /root/mk_v2 && setsid /root/miniconda3/bin/python -u "
    "_b9_stage1_chain.py >> /root/mk_v2_runs/e3_b9_calib/stage1_chain_stdout.log "
    "2>&1 < /dev/null & echo LAUNCHED $!; exit 0"
)

launch = "--launch" in sys.argv

c = _remote.connect()
sftp = c.open_sftp()
for local, remote in FILES.items():
    sftp.put(str(Path(__file__).resolve().parent / local), remote)
    print("uploaded %-24s -> %s" % (local, remote))
sftp.close()

print("\n#### syntax + self-test of the deployed copies")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile "
               "_b9_aggregate.py _b9_stage1_chain.py && echo COMPILE_OK",
            timeout=300)
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _b9_aggregate.py "
               "--self-test", timeout=300)

print("\n#### aggregation over the rows on disk (read-only)")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _b9_aggregate.py",
            timeout=600)

if launch:
    print("\n#### launching the stage-1 chainer (detached)")
    _remote.run(c, LAUNCH, timeout=180)
    _remote.run(c, "sleep 8; tail -20 "
                   "/root/mk_v2_runs/e3_b9_calib/stage1_chain.log", timeout=180)
else:
    print("\n(not launched; pass --launch)")
c.close()
print("\nDEPLOY_DONE")
