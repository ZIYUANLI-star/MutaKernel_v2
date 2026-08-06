import time
import _remote

E1 = "/root/mk_v2_runs/e1"
LEDGERS = (f"{E1}/cse_observations_lane3.jsonl {E1}/cse_completed_lane3.json "
           f"{E1}/cse_observations_lane5.jsonl {E1}/cse_completed_lane5.json")

c = _remote.connect()
print("--- post-drill verification ---")
_remote.run(c, f"md5sum {LEDGERS}", timeout=60)
_remote.run(c,
    f"ls {E1}/FINAL_WINDOW_DONE 2>/dev/null && echo BAD_DONE_CREATED || echo NO_DONE_MARK_OK; "
    "ls -d /root/mk_v2_runs/final_window.lock 2>/dev/null && echo BAD_GO_LOCK || echo NO_GO_LOCK_OK; "
    "ls -d /root/mk_v2_runs/final_window_trigger_drill.lock 2>/dev/null && echo DRILL_LOCK_LEFT || echo DRILL_LOCK_CLEANED_OK; "
    f"rm -f {E1}/FW_DRILL_FAKE_MARK; ls {E1}/FW_DRILL_FAKE_MARK 2>/dev/null || echo FAKE_MARK_REMOVED_OK; "
    f"ls {E1}/final_window_review 2>/dev/null && echo REVIEW_DIR_EXISTS || echo NO_REVIEW_DIR_OK",
    timeout=60)

print("--- arm real trigger ---")
_remote.run(c,
    "cd /root/mk_v2 && nohup bash /root/mk_v2/_final_window_trigger.sh "
    "</dev/null >/dev/null 2>&1 & echo ARM_SENT",
    timeout=30)
time.sleep(3)
print("--- real trigger self-check ---")
_remote.run(c, "pgrep -af 'final_window_trigger.sh' ; true", timeout=30)
_remote.run(c, "cat /root/mk_v2_runs/final_window_trigger.log", timeout=30)
_remote.run(c,
    "ls -d /root/mk_v2_runs/final_window_trigger.lock && "
    "ps -o pid,etime,args -p 200586 91971 108721 2>/dev/null",
    timeout=30)
c.close()
print("ARM_DONE")
