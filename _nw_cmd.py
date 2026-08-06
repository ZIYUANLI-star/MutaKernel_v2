"""Run an arbitrary remote command (read from a local file to dodge quoting)."""
import sys

import _remote

path = sys.argv[1]
timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 600
cmd = open(path, encoding="utf-8").read()
c = _remote.connect()
_remote.run(c, cmd, timeout=timeout)
c.close()
