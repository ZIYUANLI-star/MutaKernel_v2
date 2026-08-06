import _remote, os, sys

c = _remote.connect()
R = "/root/mk_v2_runs/e1/witness_confirmation"
cmds = [
    "date",
    f"ls -la {R} | head -60",
    f"ls {R}/cells | wc -l",
    f"ls /root/mk_v2/_wc*.py | head -40",
    f"ls -la /root/mk_v2/_wc_audit.py /root/mk_v2/_wc_start.py /root/mk_v2/_wc_analyze.py",
    "ps -eo pid,ppid,pgid,etime,stat,args | grep -E '_wc_(audit|start)' | grep -v grep",
    f"tail -30 {R}/*.log 2>/dev/null | tail -80",
]
for cmd in cmds:
    print("### " + cmd)
    _remote.run(c, cmd, timeout=120)
c.close()
print("DONE_RECON1")
