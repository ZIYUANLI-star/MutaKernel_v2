import _remote

c = _remote.connect()
CMDS = [
    "grep -n 'def \\|POLICY\\|policies' /root/mk_v2/scripts/run_e1_probe_study.py | sed -n '1,60p'",
    "sed -n '660,780p' /root/mk_v2/scripts/run_e1_probe_study.py",
]
for cmd in CMDS:
    _, o, _ = _remote.run(c, cmd, timeout=90, echo=False)
    print(o)
    print('====')
c.close()
print('RQ_INSPECT5_DONE')
