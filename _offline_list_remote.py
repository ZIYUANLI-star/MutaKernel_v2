"""List /root/mk_v2_runs/e1 top-level files (read-only recon for offline analysis)."""
from _remote import connect, run

c = connect()
run(c, "ls -la --time-style=+%F_%T /root/mk_v2_runs/e1/ | grep -v '^d' | awk '{print $5, $6, $7}'", timeout=60)
run(c, "ls /root/mk_v2_runs/e1/ | head -100", timeout=60)
run(c, "wc -l /root/mk_v2_runs/e1/*.jsonl 2>/dev/null", timeout=60)
run(c, "ls /root/mk_v2_runs/e1/analysis 2>/dev/null || echo NO_ANALYSIS_DIR", timeout=60)
c.close()
print("LIST_DONE")
