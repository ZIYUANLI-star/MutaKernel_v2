"""v1.12 survey step 1: read-only inventory of /root/mk_v2_runs/e1/ final state."""
import _remote

REMOTE_PY = "/root/miniconda3/bin/python"

c = _remote.connect()
cmds = [
    "ls -la /root/mk_v2_runs/e1/ | head -60",
    "cat /root/mk_v2_runs/e1/final_window_summary.json",
    "md5sum /root/mk_v2_runs/e1/baseline_observations.jsonl",
    "wc -l /root/mk_v2_runs/e1/cse_observations*.jsonl /root/mk_v2_runs/e1/*inc_archive*.jsonl 2>/dev/null",
    "ls /root/mk_v2_runs/e1/final_window_review/ 2>/dev/null",
    "cat /root/mk_v2_runs/e1/equiv_summary.json 2>/dev/null | head -50",
]
for cmd in cmds:
    print("### " + cmd)
    _remote.run(c, cmd, timeout=180)
c.close()
print("SURVEY_DONE")
