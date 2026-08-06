import _remote as R

c = R.connect()
R.run(c, "grep -n 'def \\|STRESS_POLICIES\\|^class ' /root/mk_v2/src/stress/policy_bank.py | head -50", timeout=60)
R.run(c, "sed -n '1,60p' /root/mk_v2/src/stress/policy_bank.py", timeout=60)
c.close()
print("DONE")
