"""Inspect the escape-mechanism classifier label space in run_e1_probe_study."""
import _remote as R

c = R.connect()
R.run(c, "grep -n 'ACTIVATION_FAILURE\\|ABSORPTION\\|MODE_\\|NONDET\\|CONFIG' "
         "/root/mk_v2/scripts/run_e1_probe_study.py | head -20", timeout=60)
R.run(c, "grep -n 'def .*escape\\|escape' /root/mk_v2/scripts/run_e1_probe_study.py "
         "| head -15", timeout=60)
c.close()
print("DONE")
