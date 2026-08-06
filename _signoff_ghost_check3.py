import _remote

CMD = "sed -n '209,340p' /root/mk_v2/_signoff_go.py"
c = _remote.connect()
_remote.run(c, CMD, timeout=120)
c.close()
