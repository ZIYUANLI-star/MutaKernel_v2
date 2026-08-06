"""Deep health check of the witness-confirmation run (read-only)."""
import _remote

CMD1 = (
    "cat /root/mk_v2_runs/e1/witness_confirmation/plan.json 2>/dev/null | head -c 3000; echo SEP; "
    "ls -la /root/mk_v2_runs/e1/witness_confirmation/; echo SEP; "
    "head -c 5000 /root/mk_v2/_wc_audit.py 2>/dev/null; ls /root/mk_v2/_wc*.py 2>/dev/null"
)

CMD2 = (
    "cat /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log; echo SEP; "
    "cat /root/mk_v2_runs/e1/witness_confirmation/audit_lane1.log; echo SEP; "
    "cat /root/mk_v2_runs/e1/witness_confirmation/*result*.jsonl /root/mk_v2_runs/e1/witness_confirmation/*record*.jsonl 2>/dev/null | head -c 3000"
)

CMD3 = (
    "nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo SEP; "
    "ps aux | grep -E '_wc|_mutant_worker' | grep -v grep; echo SEP; "
    "grep -c 'oom_kill' /dev/null 2>/dev/null; "
    "for p in /sys/fs/cgroup/memory.events /sys/fs/cgroup/memory/memory.oom_control; do "
    "grep -H 'oom_kill' $p 2>/dev/null; done; echo SEP; "
    "free -g | sed -n 2p; uptime; echo SEP; "
    "tail -c 600 /root/mk_v2_runs/e1_sentinel.log"
)

c = _remote.connect()
print("##### PLAN & CODE #####")
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print("##### FULL LANE LOGS #####")
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
print(o)
print("##### RESOURCES #####")
_, o, _ = _remote.run(c, CMD3, timeout=120, echo=False)
c.close()
print(o)
print("HEALTH_DONE")
