import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, "sed -n '532,595p' /root/mk_v2/scripts/run_e1_probe_study.py",
                      timeout=60, echo=False)
print(o)
_, o, _ = _remote.run(c, "sed -n '100,140p' /root/mk_v2/scripts/run_e1_cse_falsify.py",
                      timeout=60, echo=False)
print(o)
c.close()
print('DONE8')
