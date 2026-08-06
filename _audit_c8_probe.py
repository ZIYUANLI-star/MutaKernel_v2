"""Probe E1 infra reusability for C8 (L3 + backward)."""
import _remote as R

c = R.connect()
print("### e1 probe study script args")
R.run(c, "ls /root/mk_v2/scripts/ | grep -i 'e1\\|probe'", timeout=60)
R.run(c, "grep -n 'add_argument' /root/mk_v2/scripts/run_e1_probe_study.py 2>/dev/null | head -25", timeout=60)
print("### does the probe worker support backward?")
R.run(c, "grep -rn 'backward' /root/mk_v2/scripts/run_e1_probe_study.py 2>/dev/null | head -10", timeout=60)
R.run(c, "grep -rln 'backward' /root/mk_v2/src/experiments/ | head", timeout=60)
print("### e1 manifest builder / how subjects were fed")
R.run(c, "grep -rn 'level1\\|level2\\|task_file\\|manifest' /root/mk_v2/scripts/run_e1_probe_study.py 2>/dev/null | head -15", timeout=60)
print("### fse runner backward support")
R.run(c, "grep -rn 'backward' /root/mk_v2/scripts/run_fse_experiment.py | head -10", timeout=60)
c.close()
print("C8_PROBE_DONE")
