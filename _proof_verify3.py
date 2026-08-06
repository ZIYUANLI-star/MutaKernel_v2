"""Inspect probes dir for the proven probes' mutant payloads."""
import _remote as R

c = R.connect()
cmds = [
    "ls /root/mk_v2_runs/e1/probes/ | head; ls /root/mk_v2_runs/e1/probes/ | wc -l",
    "ls /root/mk_v2_runs/e1/probes/ | grep -E 'L1_P1_|L1_P6_|L1_P14_|L1_P21_|L2_P64_' | head -20",
]
for cmd in cmds:
    print("### " + cmd[:90])
    R.run(c, cmd, timeout=120)
c.close()
print("DONE")
