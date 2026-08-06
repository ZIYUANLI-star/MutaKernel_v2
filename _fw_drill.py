import _remote

E1 = "/root/mk_v2_runs/e1"
LEDGERS = (f"{E1}/cse_observations_lane3.jsonl {E1}/cse_completed_lane3.json "
           f"{E1}/cse_observations_lane5.jsonl {E1}/cse_completed_lane5.json")
FAKE = f"{E1}/FW_DRILL_FAKE_MARK"
DLOG = "/root/mk_v2_runs/final_window_trigger_drill.log"
DLOCK = "/root/mk_v2_runs/final_window_trigger_drill.lock"

c = _remote.connect()
print("--- pre-drill ledger md5 ---")
_, pre, _ = _remote.run(c, f"md5sum {LEDGERS}", timeout=60, echo=True)
_remote.run(c, f"rm -f {FAKE} {DLOG}; rmdir {DLOCK} 2>/dev/null; "
               f"ls {E1}/final_window_review 2>/dev/null; "
               f"ls {E1}/FINAL_WINDOW_DONE 2>/dev/null; echo PRECLEAN_OK",
            timeout=60)

print("--- start drill trigger (fake mark, --dry-run) ---")
_remote.run(c,
    f"cd /root/mk_v2 && nohup env FW_MARK={FAKE} FW_LOG={DLOG} FW_LOCK={DLOCK} "
    f"FW_GO_ARGS=--dry-run bash /root/mk_v2/_final_window_trigger.sh "
    f">/dev/null 2>&1 & sleep 2; pgrep -af '_final_window_trigger' || echo NO_TRIGGER_PROC",
    timeout=60)

print("--- drop fake marker, wait for end-to-end dry-run ---")
_remote.run(c,
    f"touch {FAKE}; "
    "for i in $(seq 1 60); do "
    f"  grep -q FINAL_WINDOW_TRIGGERED_OK {DLOG} 2>/dev/null && break; sleep 10; "
    "done; "
    f"grep -c FINAL_WINDOW_TRIGGERED_OK {DLOG} || echo DRILL_TIMED_OUT",
    timeout=700)

print("--- drill log ---")
_remote.run(c, f"cat {DLOG}", timeout=60)

print("--- post-drill checks ---")
_, post, _ = _remote.run(c, f"md5sum {LEDGERS}", timeout=60, echo=True)
print("LEDGER_UNCHANGED:", pre == post)
_remote.run(c,
    f"ls {E1}/FINAL_WINDOW_DONE 2>/dev/null && echo BAD_DONE_CREATED || echo NO_DONE_MARK_OK; "
    f"ls -d /root/mk_v2_runs/final_window.lock 2>/dev/null && echo BAD_LOCK_LEFT || echo NO_GO_LOCK_OK; "
    f"ls -d {DLOCK} 2>/dev/null && echo DRILL_LOCK_LEFT || echo DRILL_LOCK_CLEANED_OK; "
    f"pgrep -af '_final_window_trigger' || echo TRIGGER_EXITED_OK; "
    f"rm -f {FAKE}; ls {FAKE} 2>/dev/null || echo FAKE_MARK_REMOVED_OK; "
    # untouched: lane3 driver / guard / sentinel
    "ps -o pid,args -p 200586 91971 108721 2>/dev/null",
    timeout=60)
c.close()
print("DRILL_DONE")
