#!/usr/bin/env python3
import _remote

c = _remote.connect()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m pytest "
               "tests/test_validation_core.py 2>&1 | tail -25", timeout=600)
c.close()
