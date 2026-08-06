"""Step 2: how does the runner resume? detected_pairs population + manifest checks."""
import _remote as R

c = R.connect()
print("### detected_pairs population")
R.run(c, "grep -n -B4 -A6 'detected_pairs' /root/mk_v2/scripts/run_fse_experiment.py",
      timeout=60)
print("### resume / existing manifest handling")
R.run(c, "grep -n -B3 -A10 'run_manifest\\|resume\\|completed_case\\|existing' "
         "/root/mk_v2/scripts/run_fse_experiment.py | sed -n '1,120p'",
      timeout=60)
c.close()
print("STEP2_DONE")
