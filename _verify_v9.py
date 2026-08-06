import _remote

CMD = (
    "cat /root/mk_v2_runs/e1_guard.pid 2>/dev/null; "
    "ps aux | grep 'guard_cse_[s]plit' | grep -v grep | wc -l; echo SEP; "
    "ps aux | grep 'run_e1_cse_[f]alsify' | grep -v grep; echo SEP; "
    "free -g | sed -n 2p; nvidia-smi --query-gpu=memory.used --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo SEP; "
    "tail -2 /root/mk_v2_runs/e1_cse_lane3.log; tail -2 /root/mk_v2_runs/e1_cse_lane5.log"
)

c = _remote.connect()
_, out, _ = _remote.run(c, CMD, timeout=300, echo=False)
c.close()
print(out)
print("VERIFY_DONE")
