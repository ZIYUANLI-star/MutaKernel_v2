#!/usr/bin/env python3
"""Read-only: guard script content."""
import _remote

c = _remote.connect()
_remote.run(c, "cat /root/mk_v2_runs/e1_guard_cse_split.sh", timeout=60)
c.close()
