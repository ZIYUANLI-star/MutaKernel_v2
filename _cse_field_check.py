import _remote

CMD = (
    "free -g | head -2; echo SEP; "
    "nvidia-smi --query-gpu=memory.used --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo SEP; "
    "ps aux | grep -E 'run_e1_cse_[f]alsify|guard_cse' | grep -v grep; echo SEP; "
    "ls /root/mk_v2_runs/*.pid 2>/dev/null; cat /root/mk_v2_runs/e1_guard_cse*.pid 2>/dev/null; echo SEP; "
    "wc -l /root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
    "/root/mk_v2_runs/e1/cse_observations_lane4.jsonl "
    "/root/mk_v2_runs/e1/cse_observations_lane5.jsonl"
)

c = _remote.connect()
_, out, _ = _remote.run(c, CMD, timeout=300, echo=False)
print(out)
print("====GUARD SCRIPT====")
s = c.open_sftp()
try:
    with s.open("/root/mk_v2_runs/e1_guard_cse_split.sh") as f:
        print(f.read().decode())
except Exception as e:
    print("guard read fail:", e)
s.close()
c.close()
