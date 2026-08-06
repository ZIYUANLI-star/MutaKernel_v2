import _remote

CMD = (
    "ps aux | grep 'run_e1_probe_[s]tudy' | grep -v grep | wc -l; echo SEP; "
    "wc -l < /root/mk_v2_runs/e1/equiv_observations_lane4_requeue.jsonl 2>/dev/null; echo SEP; "
    "tail -c 900 /root/mk_v2_runs/e1_equiv_lane4_requeue.log; echo SEP; "
    "grep -ci 'out of memory\\|CUDA error\\|Traceback\\|AUTORESTART' "
    "/root/mk_v2_runs/e1_equiv_lane4_requeue.log; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo SEP; "
    "grep -h '\"evidence_grade\"' /root/mk_v2_runs/e1/equiv_observations_lane4_requeue.jsonl "
    "2>/dev/null | grep -o '\"evidence_grade\": \"[A-Z_]*\"' | sort | uniq -c"
)

c = _remote.connect()
_, out, _ = _remote.run(c, CMD, timeout=180, echo=False)
c.close()
print(out)
