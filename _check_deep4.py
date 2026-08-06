import _remote as R

c = R.connect()
print("### context around line 863")
R.run(c, "sed -n '840,880p' /root/mk_v2/scripts/run_fse_experiment.py", timeout=60)
print("### context around line 520-560 (worker spawn)")
R.run(c, "sed -n '520,560p' /root/mk_v2/scripts/run_fse_experiment.py", timeout=60)
c.close()
print("DONE")
