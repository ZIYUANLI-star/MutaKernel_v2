"""Find per-probe mutant sources for the proven probes."""
import _remote as R

c = R.connect()
cmds = [
    "ls /root/mk_v2_runs/e1/ | head -40",
    "find /root/mk_v2_runs/e1 -maxdepth 2 -type d | head -20",
    "find /root/mk_v2_runs/e1 -name '*L1_P1__const_perturb__0*' 2>/dev/null | head",
    "grep -l 'L1_P1__const_perturb__0' /root/mk_v2_runs/e1/*.jsonl 2>/dev/null",
]
for cmd in cmds:
    print("### " + cmd[:90])
    R.run(c, cmd, timeout=120)
c.close()
print("DONE")
