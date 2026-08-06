"""Is there any C4 / TritonBench contract or B9 plan? Plus critical-path progress."""
import _remote

c = _remote.connect()
for cmd in [
    "echo '== any C4 / triton contract artifacts =='; ls -la /root/mk_v2_runs/e2/ 2>&1 | head -40",
    "find /root/mk_v2_runs -maxdepth 2 -iname '*C4*' -o -maxdepth 2 -iname '*triton*' 2>/dev/null | head -20",
    "ls /root/mk_v2/configs/ 2>&1 | head -30",
    "echo '== contracts on disk =='; find /root/mk_v2_runs -maxdepth 2 -name 'contracts*' 2>/dev/null",
    "echo '== e3_c6 =='; ls -la /root/mk_v2_runs/e3_c6/ 2>&1 | head -20",
    "echo '== critical path progress =='; tail -6 /root/mk_v2_runs/e1/e1_cse_lane3_signoff_requeue.log 2>&1",
    "echo '== signoff completed =='; cat /root/mk_v2_runs/e1/cse_completed_lane3_signoff_requeue.json 2>&1",
    "echo '== orch log =='; tail -6 /root/mk_v2_runs/signoff_orch.log 2>&1",
    "echo '== chain trigger =='; tail -3 /root/mk_v2_runs/e3_b9_calib/chain_trigger.log",
    "date -Iseconds; grep -i oom /proc/vmstat",
]:
    print("\n#### " + cmd[:78])
    _remote.run(c, cmd, timeout=180)
c.close()
print("\nH13_DONE")
