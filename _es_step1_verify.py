"""Step 1: verify early-stop flag, strategy names, env capture method."""
import _remote as R

c = R.connect()
print("### runner CLI flags")
R.run(c, "grep -n 'add_argument\\|early' /root/mk_v2/scripts/run_fse_experiment.py | head -30",
      timeout=60)
print("### early-stop semantics")
R.run(c, "grep -n -B2 -A8 'early_stop\\|early-stop' /root/mk_v2/scripts/run_fse_experiment.py | head -60",
      timeout=60)
print("### strategy names in obs")
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"" 
         "import glob,json;from collections import Counter;"
         "s=Counter();"
         "[s.update([json.loads(l).get('strategy_name')]) "
         "for f in glob.glob('/root/mk_v2_runs/e3_campaign/**/observations.jsonl',recursive=True) "
         "for l in open(f) if l.strip()];print(dict(s))\"", timeout=120)
print("### guard script")
R.run(c, "cat /root/mk_v2/guard_lane_m.sh", timeout=60)
print("### how env manifest was captured")
R.run(c, "ls /root/mk_v2/scripts/ | grep -i 'env\\|capture'", timeout=60)
c.close()
print("STEP1_DONE")
