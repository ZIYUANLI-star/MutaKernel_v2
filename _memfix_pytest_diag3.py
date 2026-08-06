#!/usr/bin/env python3
import _remote

c = _remote.connect()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m pytest -q "
               "2>&1 | sed -n '/= ERRORS =/,/short test summary/p' | head -60",
            timeout=600)
c.close()
