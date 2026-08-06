"""Fetch remote files into _nw_ref/ for local reading (new-witness review)."""
import os
import sys

import _remote

FILES = sys.argv[1:]
os.makedirs("_nw_ref", exist_ok=True)
c = _remote.connect()
sftp = c.open_sftp()
for f in FILES:
    local = os.path.join("_nw_ref", os.path.basename(f))
    try:
        sftp.get(f, local)
        print("OK", f, "->", local, os.path.getsize(local))
    except Exception as exc:
        print("FAIL", f, exc)
sftp.close()
c.close()
