import _remote

c = _remote.connect()
code, o, e = _remote.run(c, "sed -n '60,190p' /root/mk_v2/scripts/run_e1_cse_falsify.py", timeout=60, echo=False)
print(o)
c.close()
