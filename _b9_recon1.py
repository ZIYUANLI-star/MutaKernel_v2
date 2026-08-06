# -*- coding: utf-8 -*-
"""B9 calibration pre-flight recon: E1 wrap-up verification (read-only) +
E3 remote state (contracts drafts, smoke dirs, corpus presence)."""
import _remote as R

c = R.connect()
cmds = [
    # --- E1 wrap-up verification (all read-only) ---
    ("e1 markers", "ls -la /root/mk_v2_runs/e1/FINAL_WINDOW_DONE "
     "/root/mk_v2_runs/e1/CSE_DONE* 2>&1"),
    ("final window summary", "cat /root/mk_v2_runs/e1/final_window_summary.json 2>&1 | head -40"),
    ("final window log tail", "tail -6 /root/mk_v2_runs/final_window.log 2>&1"),
    ("leftover e1 processes", "ps aux | grep -E 'final_window|trigger|run_e1|mutant_worker|guard' "
     "| grep -v grep; echo ---; ps -p 108721 -o pid,etime,cmd 2>&1"),
    ("gpu idle?", "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv; "
     "nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>&1"),
    # --- E3 state ---
    ("runs dirs", "ls /root/mk_v2_runs/ | grep -Ei 'e3|contract|e2' ; echo ---; ls /root/mk_v2_runs/ | tail -30"),
    ("e3 smoke dirs", "ls -la /root/mk_v2_runs/e3_smoke/ /root/mk_v2_runs/e3_smoke_cal/ 2>&1 | head -30"),
    ("contract drafts", "find /root/mk_v2_runs /root/mk_v2/contracts -maxdepth 3 -name 'contracts*' 2>/dev/null | head; "
     "echo ---; wc -l /root/mk_v2_runs/*/contracts_c2c3c5_draft.jsonl 2>/dev/null; "
     "find / -maxdepth 4 -name 'contracts_c2c3c5_draft*' 2>/dev/null | head"),
    ("collection frames", "ls -la /root/mk_v2_runs/e2_reconcile/ 2>&1 | head -20"),
    ("repo state", "cd /root/mk_v2 && git log --oneline -3 2>/dev/null; ls scripts/run_e3_external.py src/experiments/external_ports/"),
    ("disk/mem", "df -h /root | tail -1; free -g | sed -n 2p; nproc"),
]
for name, cmd in cmds:
    print("### " + name)
    R.run(c, cmd, timeout=180)
c.close()
print("B9_RECON1_DONE")
