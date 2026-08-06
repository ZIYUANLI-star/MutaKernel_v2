"""Dry-run the exact command the trigger will fire (read-only)."""
import _remote

c = _remote.connect()
print("#### resume_b9.sh --lanes 2 --limit 13 --budget-gb 100 --dry-run")
_remote.run(c, "cd /root/mk_v2_runs/e3_b9_calib && bash resume_b9.sh --lanes 2 "
               "--limit 13 --budget-gb 100 --dry-run 2>&1 | "
               "sed -n '/=== resume plan/,$p'", timeout=600)
c.close()
print("\nH18_DONE")
