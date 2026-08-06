"""Check the first records of restarted lanes 3/4/5 (3600s budget)."""
import _remote

REMOTE = r'''
import json
from pathlib import Path
E1 = Path("/root/mk_v2_runs/e1")
for lane in (3, 4, 5):
    obs = E1 / f"cse_observations_lane{lane}.jsonl"
    rows = ([json.loads(l) for l in open(obs, encoding="utf-8") if l.strip()]
            if obs.exists() else [])
    print(f"--- lane {lane}: {len(rows)} records ---")
    for r in rows[:4]:
        print(json.dumps({
            "probe_id": r["probe_id"], "outcome": r["outcome"],
            "wall_s": round(r["wall_ms"] / 1000),
            "timed_out": r["timed_out"],
            "valid_rounds": r.get("valid_rounds"),
            "witness_policy": r.get("witness_policy"),
            "evidence": r.get("evidence"),
        }))
'''

c = _remote.connect()
sftp = c.open_sftp()
import io
sftp.putfo(io.BytesIO(REMOTE.encode()), "/root/mk_v2/_cse_first_remote.py")
sftp.close()
_remote.run(c, "date '+%F %T %z'; /root/miniconda3/bin/python /root/mk_v2/_cse_first_remote.py", timeout=60)
_remote.run(c, "grep -ciE 'traceback|out of memory|AUTORESTART' /root/mk_v2_runs/e1_cse_lane3.log /root/mk_v2_runs/e1_cse_lane4.log /root/mk_v2_runs/e1_cse_lane5.log || true; "
               "nvidia-smi --query-gpu=memory.used --format=csv,noheader", timeout=30)
c.close()
print("FIRSTPROBE_DONE")
