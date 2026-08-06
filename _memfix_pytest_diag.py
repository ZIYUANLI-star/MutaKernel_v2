#!/usr/bin/env python3
import _remote

c = _remote.connect()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -m pytest -q "
               "2>&1 | grep -B2 -A12 'ERROR tests/test_validation_core' "
               "| head -40", timeout=600)
c.close()
