"""Deploy the brake protocol and run its test in a scratch dir (no prod impact)."""
from pathlib import Path

import _remote

FILES = {
    "_b9_brake.py": "/root/mk_v2/_b9_brake.py",
    "_b9_brake_test.py": "/root/mk_v2/_b9_brake_test.py",
}

c = _remote.connect()
sftp = c.open_sftp()
here = Path(__file__).resolve().parent
for local, remote in FILES.items():
    sftp.put(str(here / local), remote)
    print("uploaded %-22s -> %s" % (local, remote))
sftp.close()

print("\n#### syntax")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m py_compile "
               "_b9_brake.py _b9_brake_test.py && echo COMPILE_OK", timeout=300)

print("\n#### protocol test (scratch dir; the real markers are untouched)")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u "
               "_b9_brake_test.py", timeout=600)

print("\n#### status against the REAL run directory (read + sync only)")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _b9_brake.py status",
            timeout=300)
c.close()
print("\nBRAKE_DEPLOY_DONE")
