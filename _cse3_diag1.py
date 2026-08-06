#!/usr/bin/env python3
"""Upload and run the forensics script on the A800."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_cse3_diag_remote.py", "/tmp/_cse3_diag_remote.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /tmp/_cse3_diag_remote.py",
            timeout=300)
c.close()
