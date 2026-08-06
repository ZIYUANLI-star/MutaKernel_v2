"""Inspect remote ledger state before executing the sign-off."""
import _remote

CMDS = [
    "ls -la /root/mk_v2_runs/e1/ | head -60",
    "ls -la /root/mk_v2_runs/e1/final_window_review/ 2>/dev/null",
    "cat /root/mk_v2_runs/e1/final_window_review/final_window_summary.json 2>/dev/null",
    "ls /root/mk_v2_runs/e1/cse_observations*.jsonl 2>/dev/null; "
    "for f in /root/mk_v2_runs/e1/cse_observations*.jsonl; do echo \"$f $(wc -l < $f)\"; done",
    "ls /root/mk_v2_runs/e1/equiv_observations*.jsonl 2>/dev/null; "
    "for f in /root/mk_v2_runs/e1/equiv_observations*.jsonl; do echo \"$f $(wc -l < $f)\"; done",
    "ps aux | grep -E 'sentinel|trigger|guard' | grep -v grep",
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; free -g | sed -n 2p",
]

c = _remote.connect()
for cmd in CMDS:
    print("### " + cmd)
    _remote.run(c, cmd, timeout=120)
    print()
c.close()
print("INSPECT_DONE")
