"""Fetch deployed B9 control scripts + calibration state for review."""
import _remote

c = _remote.connect()
cmds = [
    "echo '===== resume_b9.sh'; cat /root/mk_v2_runs/e3_b9_calib/resume_b9.sh",
    "echo '===== pause_b9.sh'; cat /root/mk_v2_runs/e3_b9_calib/pause_b9.sh",
    "echo '===== guard_b9_v2.sh'; cat /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.sh",
    "echo '===== _b9_precheck.py'; cat /root/mk_v2/_b9_precheck.py 2>&1 || find /root -maxdepth 3 -name '_b9_precheck.py' 2>/dev/null",
    "echo '===== run_manifest'; cat /root/mk_v2_runs/e3_b9_calib/run_manifest.json",
    "echo '===== completed lanes'; for f in /root/mk_v2_runs/e3_b9_calib/completed_lane*.json; do echo \"-- $f\"; cat $f; echo; done",
    "echo '===== cgroup mem'; cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.current 2>/dev/null; echo '--events'; cat /sys/fs/cgroup/memory.events 2>/dev/null; echo '--v1'; cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null",
    "echo '===== signoff orch tail'; tail -30 /root/mk_v2_runs/signoff_orch_stdout.log 2>&1",
    "echo '===== signoff driver log tail'; ls -t /root/mk_v2_runs/e1/*signoff*log 2>/dev/null | head -3",
]
for cmd in cmds:
    print("\n" + "#" * 4 + " " + cmd[:70])
    _remote.run(c, cmd, timeout=180)
c.close()
print("\nH2_DONE")
