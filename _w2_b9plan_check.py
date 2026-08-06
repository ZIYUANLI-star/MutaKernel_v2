import _remote as R

c = R.connect()
R.run(c, "grep -rn 'def plan_b9_port' /root/mk_v2/src /root/mk_v2/scripts | head", timeout=60)
R.run(c, "grep -rn 'def plan_b9_port' -A 25 /root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py 2>/dev/null | head -40", timeout=60)
c.close()
print("DONE")
