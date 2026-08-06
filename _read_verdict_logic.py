import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, "sed -n '128,250p' /root/mk_v2/_wc_analyze.py", timeout=60, echo=False)
c.close()
print(o)
