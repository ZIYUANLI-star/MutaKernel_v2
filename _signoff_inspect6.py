import _remote

CMD = "sed -n '100,310p' /root/mk_v2/_final_window_go.py"
c = _remote.connect()
_remote.run(c, CMD, timeout=120)
c.close()
