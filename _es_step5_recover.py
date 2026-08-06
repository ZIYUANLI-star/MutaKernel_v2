"""Step 5: recover - assess state, stop strays, commit with inline identity,
capture env v2, update guard, verify clean tree."""
import _remote as R

c = R.connect()
print("### state check")
R.run(c, "pgrep -af 'guard_[l]ane_m|run_fse_[e]xperiment' || echo NOTHING_RUNNING; "
         "ls /root/mk_v2_runs/e3_campaign/LANE_M_STOP 2>/dev/null && echo STOP_PRESENT; "
         "cd /root/mk_v2 && git log -1 --format='%h %an <%ae>' && git status --porcelain",
      timeout=60)
print("### stop any stray guard/runner")
R.run(c, "touch /root/mk_v2_runs/e3_campaign/LANE_M_STOP; "
         "pkill -f 'guard_[l]ane_m'; pkill -f 'run_fse_[e]xperiment'; "
         "pkill -f '_candidate_[w]orker'; sleep 3; "
         "pgrep -af 'guard_[l]ane_m|run_fse_[e]xperiment|_candidate_[w]orker' "
         "|| echo ALL_CLEAR", timeout=60)
c.close()
print("RECOVER1_DONE")
