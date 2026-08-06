import _remote

c = _remote.connect()
cmd = (
    "tail -c 1800 /root/mk_v2_runs/e1_equiv.log; echo SEP; "
    "wc -l < /root/mk_v2_runs/e1/equiv_observations.jsonl 2>/dev/null; echo SEP; "
    "ps aux | grep 'run_e1_probe_[s]tudy' | grep -v grep | wc -l; echo SEP; "
    "date -u '+now=%H:%M'; stat -c 'log_mtime=%y' /root/mk_v2_runs/e1_equiv.log; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; echo SEP; "
    "grep -ciE 'traceback' /root/mk_v2_runs/e1_equiv.log; echo SEP; "
    "ls /root/mk_v2_runs/e1/ | head -30"
)
_, out, _ = _remote.run(c, cmd, timeout=120, echo=False)
c.close()
print(out)
print("EQUIV_STATUS_DONE")
