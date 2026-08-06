import time

import _remote

c = _remote.connect()
s = c.open_sftp()
s.put("_dl_final_window_go.py", "/root/mk_v2/_final_window_go.py")
s.put("_dl_final_window_trigger.sh", "/root/mk_v2/_final_window_trigger.sh")
s.close()
print("== uploaded ==")

# Syntax gates
_remote.run(c, "chmod +x /root/mk_v2/_final_window_trigger.sh && "
               "bash -n /root/mk_v2/_final_window_trigger.sh && echo BASH_N_OK")
_remote.run(c, "/root/miniconda3/bin/python -m py_compile "
               "/root/mk_v2/_final_window_go.py && echo PY_COMPILE_OK")

# Drill: fake marker + isolated trigger instance + --dry-run orchestrator.
print("== drill start ==")
_remote.run(c,
    "rm -f /root/mk_v2_runs/final_window_trigger_drill.log; "
    "rm -rf /root/mk_v2_runs/final_window_trigger_drill.lock; "
    "touch /root/mk_v2_runs/e1/FAKE_CSE_DONE_LANE3_DRILL && "
    "nohup env FW_MARK=/root/mk_v2_runs/e1/FAKE_CSE_DONE_LANE3_DRILL "
    "FW_LOG=/root/mk_v2_runs/final_window_trigger_drill.log "
    "FW_LOCK=/root/mk_v2_runs/final_window_trigger_drill.lock "
    "FW_GO_ARGS=--dry-run "
    "/root/mk_v2/_final_window_trigger.sh >/dev/null 2>&1 & "
    "echo DRILL_TRIGGER_LAUNCHED")

for i in range(12):
    time.sleep(15)
    code, out, _ = _remote.run(
        c, "grep -c FINAL_WINDOW_TRIGGERED_OK "
           "/root/mk_v2_runs/final_window_trigger_drill.log 2>/dev/null",
        echo=False)
    if out.strip() and out.strip() != "0":
        print(f"drill finished after ~{(i + 1) * 15}s")
        break
    print(f"waiting drill ... {(i + 1) * 15}s")

print("== drill trigger log ==")
_remote.run(c, "cat /root/mk_v2_runs/final_window_trigger_drill.log")
print("== drill safety checks ==")
_remote.run(c,
    "echo lane3_driver:; ps -o pid,args -p 200586 --no-headers; "
    "echo guard:; ps -o pid,args -p 91971 --no-headers; "
    "echo FINAL_WINDOW_DONE_exists:; ls /root/mk_v2_runs/e1/FINAL_WINDOW_DONE 2>&1; "
    "echo archive_exists:; ls /root/mk_v2_runs/e1/cse_observations_inc_archive_v2.jsonl 2>&1; "
    "echo obs_lines:; wc -l /root/mk_v2_runs/e1/cse_observations_lane3.jsonl /root/mk_v2_runs/e1/cse_observations_lane5.jsonl; "
    "echo completed_sizes:; /root/miniconda3/bin/python -c \"import json; print(len(json.load(open('/root/mk_v2_runs/e1/cse_completed_lane3.json'))), len(json.load(open('/root/mk_v2_runs/e1/cse_completed_lane5.json'))))\"; "
    "rm -f /root/mk_v2_runs/e1/FAKE_CSE_DONE_LANE3_DRILL && echo FAKE_MARKER_REMOVED; "
    "ls /root/mk_v2_runs/e1/ | grep -c FAKE")
c.close()
print("DRILL_PHASE_DONE")
