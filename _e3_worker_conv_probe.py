"""Find the runner's worker conventions (ModelNew? module_fn? forward call)."""
import _remote as R

c = R.connect()
R.run(c, "grep -n 'ModelNew\\|Model\\b\\|get_inputs\\|candidate' "
         "/root/mk_v2/scripts/run_fse_experiment.py | head -30", timeout=60)
R.run(c, "grep -rn 'ModelNew' /root/mk_v2/src/experiments/ | head -15", timeout=60)
R.run(c, "ls /root/mk_v2/src/experiments/", timeout=60)
c.close()
print("WORKER_PROBE_DONE")
