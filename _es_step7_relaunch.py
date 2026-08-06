"""Step 7: relaunch guard v2, then verify runner health + early-stop active."""
import time
import _remote as R

c = R.connect()
print("### launch (detached, quick return)")
R.run(c, "rm -f /root/mk_v2_runs/e3_campaign/LANE_M_STOP "
         "/root/mk_v2_runs/e3_campaign/LANE_M_DONE; "
         "cd /root/mk_v2 && (setsid nohup ./guard_lane_m.sh >/dev/null 2>&1 &) ; "
         "echo LAUNCHED", timeout=30)
time.sleep(45)
print("### verify processes")
R.run(c, "pgrep -af 'guard_[l]ane_m'; pgrep -af 'run_fse_[e]xperiment' | head -2",
      timeout=30)
print("### verify no refusal, manifest v2 created")
R.run(c, "tail -n 2 /root/mk_v2_runs/e3_campaign/lane_m_run.log; "
         "ls -la /root/mk_v2_runs/e3_campaign/lane_m_run/run_manifest.json 2>/dev/null "
         "|| echo MANIFEST_NOT_YET; "
         "tail -n 3 /root/mk_v2_runs/e3_campaign/guard_lane_m.log", timeout=30)
c.close()
print("RELAUNCH_DONE")
