"""Read the first_kill sourcing block in run_e1_probe_study.py."""
import _remote as R

c = R.connect()
R.run(c, "sed -n '780,875p' /root/mk_v2/scripts/run_e1_probe_study.py",
      timeout=60)
c.close()
print("SRC_DONE")
