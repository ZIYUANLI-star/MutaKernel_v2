"""Midnight probe: audit progress detail."""
import _remote

CMD = (
    "date '+NOW=%F %T'; echo SEP; "
    "grep -c '\\[control\\|\\[confirm' /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log; echo SEP; "
    "awk '/audit start pid=400144/,0' /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log | tail -n 12; echo SEP; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo GPUEND; "
    "nvidia-smi --query-gpu=utilization.gpu,temperature.gpu --format=csv,noheader; echo SEP; "
    "free -g | sed -n 2p; uptime | awk -F'load average:' '{print $2}'; "
    "grep oom_kill /sys/fs/cgroup/memory/memory.oom_control; echo SEP; "
    "tail -n 2 /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log; echo SEP; "
    "tail -c 250 /root/mk_v2_runs/e1_sentinel.log"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=120, echo=False)
c.close()
print(o)
print('MIDNIGHT_PROBE_DONE')
