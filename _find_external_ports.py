import _remote as R

c = R.connect()
R.run(c, "grep -rn 'def plan_b9_port\\|def plan_b7_port\\|B9_DEFAULT_TOLERANCES' "
         "/root/mk_v2/src/ | head; "
         "ls /root/mk_v2/src/experiments/ | head -40", timeout=60)
c.close()
print("DONE")
