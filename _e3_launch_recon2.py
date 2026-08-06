"""Recon 2: CLI of the plan chain + smoke artifacts."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
for s in ("build_fse_subject_manifest.py", "plan_fse_experiment.py",
          "capture_fse_environment.py"):
    print("#### " + s)
    R.run(c, f"{P} /root/mk_v2/scripts/{s} --help 2>&1 | head -40", timeout=120)
print("#### smoke dir")
R.run(c, "ls -la /root/mk_v2_runs/e3_campaign/smoke/ && "
         "head -c 1200 /root/mk_v2_runs/e3_campaign/smoke/*.json | head -50",
      timeout=60)
c.close()
print("RECON2_DONE")
