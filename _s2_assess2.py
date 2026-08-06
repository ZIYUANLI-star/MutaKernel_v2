import _remote

c = _remote.connect()
CMDS = [
    "ls /root/mk_v2_runs/ ; echo ---; ls /root/mk_v2_runs/e3* 2>/dev/null | head",
    "ls /root/mk_v2_runs/e3_external/ 2>/dev/null | head -40",
    "ls /root/mk_v2_runs/e3_external/b9_calib/ 2>/dev/null | head -40",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o)
    print('=====')
c.close()
print('DONE')
