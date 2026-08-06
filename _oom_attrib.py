import _remote

c = _remote.connect()
_remote.run(c, (
    "echo '--- CSE signoff rerun log (full) ---'; "
    "cat /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log; "
    "echo '--- signoff tagged obs ---'; "
    "cat /root/mk_v2_runs/e1/cse_observations_lane3_signoff_requeue.jsonl 2>/dev/null | "
    "/root/miniconda3/bin/python -c \"import sys,json; [print(json.loads(l)['probe_id'], json.loads(l).get('outcome'), json.loads(l).get('valid_rounds'), json.loads(l).get('wall_ms')) for l in sys.stdin if l.strip()]\"; "
    "echo '--- CSE worker alive ---'; ps aux | grep '_mutant_[w]orker' | awk '{print $2,$3,$4,$12}'; "
    "echo '--- B9 exit codes seen ---'; "
    "/root/miniconda3/bin/python -c \"import json,glob,collections; "
    "c=collections.Counter(); "
    "[c.update([(json.loads(l)['control_status'], json.loads(l).get('exit_code'))]) "
    "for f in glob.glob('/root/mk_v2_runs/e3_b9_calib/calibration_lane*.jsonl') "
    "for l in open(f) if l.strip()]; print(dict(c))\"; "
    "echo '--- worker_logs recent ---'; "
    "ls -t --time-style=+%H:%M /root/mk_v2_runs/e1/worker_logs/ 2>/dev/null | head -5; "
    "echo '--- mem now ---'; cat /sys/fs/cgroup/memory.current; cat /sys/fs/cgroup/memory.peak 2>/dev/null"
), timeout=180)
c.close()
