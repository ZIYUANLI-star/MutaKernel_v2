"""Read _b9_resume_prep.py (unit builder) + check for a subjects manifest."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "sed -n '60,140p' /root/mk_v2/_b9_resume_prep.py; echo ===; "
    "ls /root/mk_v2_runs/e3_b9_calib/*.json | head -20; echo ===; "
    "grep -n 'in_numel\\|task_file\\|above_quantile' /root/mk_v2/_b9_resume_prep.py | head -20"),
    timeout=60, echo=False)
print(o)
c.close()
