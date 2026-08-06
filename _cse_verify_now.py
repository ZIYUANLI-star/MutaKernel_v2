import _remote

CMD = (
    # process inventory: any duplicate drivers?
    "ps aux | grep -E 'run_e1_cse|cse_guard' | grep -v grep; echo SEP; "
    # lane observation counts
    "for f in /root/mk_v2_runs/e1/cse_observations_lane*.jsonl; do "
    "echo \"$(basename $f) $(wc -l < $f)\"; done; echo SEP; "
    # log tails
    "for f in /root/mk_v2_runs/e1_cse_lane*.log; do echo \"== $f\"; tail -c 400 $f; done; echo SEP; "
    # error scan
    "grep -ci 'out of memory\\|CUDA error\\|Traceback' /root/mk_v2_runs/e1_cse_lane*.log 2>/dev/null; echo SEP; "
    # gpu
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo SEP; "
    # merged equiv final distribution
    "ls -la /root/mk_v2_runs/e1/equiv_observations_merged.jsonl 2>/dev/null; "
    "grep -o '\"evidence_grade\": \"[A-Z_]*\"' /root/mk_v2_runs/e1/equiv_observations_merged.jsonl "
    "2>/dev/null | sort | uniq -c; echo SEP; "
    # duplicate check inside cse lanes: probe_id uniqueness
    "cat /root/mk_v2_runs/e1/cse_observations_lane*.jsonl 2>/dev/null | "
    "grep -o '\"probe_id\": \"[^\"]*\"' | sort | uniq -d | head -5"
)

c = _remote.connect()
_, out, _ = _remote.run(c, CMD, timeout=180, echo=False)
c.close()
print(out)
