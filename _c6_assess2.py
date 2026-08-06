import _remote

c = _remote.connect()
CMDS = [
    "grep -n 'def cmd_c6\\|def _c6\\|dry_run\\|dry-run' /root/mk_v2/scripts/run_e3_external.py | head -15",
    "grep -n 'c6' /root/mk_v2/scripts/run_e3_external.py | head -30",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o)
    print('=====')
c.close()
print('DONE')
