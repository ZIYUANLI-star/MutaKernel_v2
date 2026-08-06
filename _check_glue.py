import _remote as R

c = R.connect()
print("### guard_lane_m completion signal")
R.run(c, "ls /root/mk_v2_runs/e3_campaign/*.sh /root/mk_v2_runs/e3_campaign/guard* 2>/dev/null; "
         "grep -n 'DONE\\|COMPLETE\\|exit' /root/mk_v2_runs/e3_campaign/guard_lane_m.sh 2>/dev/null | head -20",
      timeout=60)
print("### matrix + manifests in campaign dir")
R.run(c, "ls /root/mk_v2_runs/e3_campaign/ | grep -i 'matrix\\|manifest\\|environment\\|plan'", timeout=60)
print("### capture_fse_environment CLI")
R.run(c, "grep -n 'add_argument' /root/mk_v2/scripts/capture_fse_environment.py | head", timeout=60)
print("### lane M runner invocation (from guard)")
R.run(c, "grep -n -A20 'run_fse_experiment' /root/mk_v2_runs/e3_campaign/guard_lane_m.sh | head -40", timeout=60)
c.close()
print("DONE")
