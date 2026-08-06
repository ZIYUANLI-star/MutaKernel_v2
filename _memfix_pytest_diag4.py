#!/usr/bin/env python3
import _remote

c = _remote.connect()
r = lambda cmd, t=600: _remote.run(c, cmd, timeout=t)
r("ls /root/mk_v2/pytest.ini /root/mk_v2/setup.cfg /root/mk_v2/pyproject.toml "
  "/root/mk_v2/tests/__init__.py /root/mk_v2/conftest.py "
  "/root/mk_v2/tests/conftest.py 2>&1")
r("ls /root/mk_v2/scripts | grep -iE '^tests|conftest' ; echo ---")
r("cd /root/mk_v2 && /root/miniconda3/bin/python -m pytest tests -q 2>&1 | tail -4")
c.close()
