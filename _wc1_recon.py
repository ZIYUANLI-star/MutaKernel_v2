"""Witness-confirmation campaign: step 1 recon.

Collect: P37 review evidence, B9 lane state, E1 witness inventory locations.
Avoids literal critical-path strings in remote commands.
"""
import _remote

c = _remote.connect()
R = _remote.run

print("=== nvidia-smi ===")
R(c, "nvidia-smi --query-gpu=index,memory.total,memory.used,utilization.gpu --format=csv,noheader")
print("=== oom_kill + mem ===")
R(c, "cat /sys/fs/cgroup/memory.events 2>/dev/null | grep -i oom; free -g | sed -n 2p")

print("=== p37 review dir ===")
R(c, "ls -la /root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness/")
print("=== review_summary.json ===")
R(c, "cat /root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness/review_summary.json")

print("=== e1 run dirs ===")
R(c, "ls -la /root/mk_v2_runs/e1/ | head -60")

print("=== b9 calib dir ===")
R(c, "ls -la /root/mk_v2_runs/e3_b9_calib/")

c.close()
print("RECON1_DONE")
