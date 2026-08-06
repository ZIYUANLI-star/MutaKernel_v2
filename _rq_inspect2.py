import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, "grep -n 'def build_cfg_resolver' /root/mk_v2/_wc_audit.py",
                      timeout=30, echo=False)
print(o)
_, o, _ = _remote.run(c, "sed -n '295,400p' /root/mk_v2/_wc_audit.py",
                      timeout=30, echo=False)
print(o)
c.close()
print('RQ_INSPECT2_DONE')
