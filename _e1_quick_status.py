import _remote

c = _remote.connect()
cmd = (
    "tail -c 1500 /root/mk_v2_runs/e1_baseline.log; echo SEP; "
    "wc -l < /root/mk_v2_runs/e1/baseline_observations.jsonl; echo SEP; "
    "ps aux | grep 'run_e1_probe_[s]tudy' | wc -l; echo SEP; "
    "date -u '+now=%H:%M:%S'; stat -c 'log_mtime=%y' /root/mk_v2_runs/e1_baseline.log; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; echo SEP; "
    "grep -ciE 'traceback' /root/mk_v2_runs/e1_baseline.log"
)
_, out, _ = _remote.run(c, cmd, timeout=120, echo=False)
c.close()
print(out)
print("QUICK_DONE")
