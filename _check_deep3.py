"""Locate cache_namespace call site + resume logic + guard details."""
import _remote as R

c = R.connect()
print("### call sites of _worker_environment / cache_namespace")
R.run(c, "grep -n 'cache_namespace\\|_worker_environment' /root/mk_v2/scripts/run_fse_experiment.py", timeout=60)
print("### resume/skip logic")
R.run(c, "grep -n 'resume\\|completed\\|already\\|skip' /root/mk_v2/scripts/run_fse_experiment.py | head -20", timeout=60)
print("### guard script full")
R.run(c, "cat /root/mk_v2/guard_lane_m.sh", timeout=60)
print("### is guard tracked in git?")
R.run(c, "cd /root/mk_v2 && git ls-files | grep -i guard", timeout=60)
c.close()
print("DEEP3_DONE")
