import _remote

c = _remote.connect()
CMDS = [
    "tail -15 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log; echo ---; "
    "tail -5 /root/mk_v2_runs/e3_b9_calib/stage1_chain_stdout.log",
    "grep -n 'PAUSED_FOR_SIGNOFF_RERUN\\|def main\\|while\\|sleep' /root/mk_v2/_b9_stage1_chain.py | head -25",
    "ls -la /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN* 2>/dev/null; "
    "stat -c '%y %n' /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN 2>/dev/null",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o)
    print('=====')
c.close()
print('DONE')
