"""Collect the 30-minute dual-lane verification report."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_e1_lane_status_remote.py", "/root/mk_v2/_e1_lane_status_remote.py")
sftp.close()
print("===== processes =====")
_remote.run(c, "ps -eo pid,etime,args | awk '/run_e1_probe_study|e1_guard|_mutant_worker/ && !/awk/ {print $1, $2, $3, $4, $NF}'", timeout=30)
print("===== status =====")
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_e1_lane_status_remote.py", timeout=120)
print("===== gpu now =====")
_remote.run(c, "nvidia-smi --query-compute-apps=pid,used_memory --format=csv; nvidia-smi --query-gpu=memory.used --format=csv,noheader", timeout=30)
c.close()
print("CHECK30_DONE")
