"""Full graded detail plus the orchestrator's round cap and budget constants."""
import io

import _remote

SCRIPT = r'''
import json, re, time
from pathlib import Path

MK = Path("/root/mk_v2")
E1 = Path("/root/mk_v2_runs/e1")
print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))

log = Path("/root/mk_v2_runs/signoff_orch.log")
for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
    if "graded detail" in line or "round" in line or "launching" in line:
        print("  ", line)

src = MK / "_signoff_orch.py"
if src.is_file():
    text = src.read_text(encoding="utf-8")
    print("\n---- orchestrator constants ----")
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"^[A-Z_]{3,}\s*=", s):
            print("  ", s[:140])

print("\n---- latest signoff observations ----")
obs = E1 / "cse_observations_lane3_signoff_requeue.jsonl"
if obs.is_file():
    rows = [json.loads(x) for x in obs.read_text().splitlines() if x.strip()]
    print("  %d rows" % len(rows))
    for r in rows:
        print("   %-34s %-26s %s"
              % (r.get("probe_id") or r.get("mutant_id"),
                 r.get("cse_status") or r.get("status"),
                 str(r.get("reason"))[:70]))

print("\n---- round-2 run dir ----")
d = E1 / "e1cse_tgsfz5hr"
if d.is_dir():
    for p in sorted(d.iterdir()):
        print("   %-58s %8d %s" % (p.name, p.stat().st_size,
                                   time.strftime("%H:%M:%S",
                                                 time.localtime(p.stat().st_mtime))))
    for p in sorted(d.glob("res_*.json")):
        print("   res content:", p.read_text()[:700])
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_so_detail.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_so_detail.py", timeout=300)
c.close()
