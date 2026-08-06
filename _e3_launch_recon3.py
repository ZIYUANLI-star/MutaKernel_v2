"""Recon 3: strategy matrix support + run_e3_external CLI + existing matrices."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
print("#### run_e3_external.py --help")
R.run(c, f"{P} /root/mk_v2/scripts/run_e3_external.py --help 2>&1 | head -50",
      timeout=120)
print("#### strategy matrix mentions in plan_fse_experiment.py")
R.run(c, "grep -n 'strategy' /root/mk_v2/scripts/plan_fse_experiment.py | head -30",
      timeout=60)
print("#### default matrix / strategies constants")
R.run(c, "grep -rn 'strategy_matrix\\|STRATEGY_MATRIX\\|strategies' "
         "/root/mk_v2/scripts/plan_fse_experiment.py | head -20", timeout=60)
print("#### existing matrix files anywhere")
R.run(c, "find /root/mk_v2 /root/mk_v2_runs -maxdepth 3 -name '*matrix*' 2>/dev/null",
      timeout=60)
print("#### e1 gpu smoke / e3_smoke dirs (what ran before)")
R.run(c, "ls /root/mk_v2_runs/e3_smoke/ 2>/dev/null | head; "
         "ls /root/mk_v2_runs/e4_mdir_smoke/ 2>/dev/null | head", timeout=60)
c.close()
print("RECON3_DONE")
