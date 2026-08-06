"""Verify the C4 contract draft and the L3 contract gap."""
import io

import _remote

SCRIPT = r'''
import json, collections
from pathlib import Path

for p in [Path("/root/mk_v2/contracts"), Path("/root/mk_v2_runs/e2_reconcile")]:
    print("== dir", p, "exists:", p.is_dir())
    if p.is_dir():
        for f in sorted(p.iterdir()):
            print("   ", f.name, f.stat().st_size)

c4 = Path("/root/mk_v2/contracts/contracts_c4_draft.jsonl")
if c4.is_file():
    rows = [json.loads(l) for l in c4.read_text().splitlines() if l.strip()]
    print("\n== C4 draft rows:", len(rows))
    print("   fields:", sorted(rows[0].keys()))
    r0 = rows[0]
    print("   sample task_key/id:", r0.get("task_key"), r0.get("task_id"))
    dt = collections.Counter()
    for r in rows:
        con = r.get("contract", {})
        dts = con.get("dtypes") or con.get("oracle", {}).get("dtype_tolerances")
        if isinstance(dts, dict):
            dt[tuple(sorted(dts))] += 1
        elif isinstance(dts, list):
            dt[tuple(sorted(dts))] += 1
        else:
            dt[str(dts)] += 1
    print("   dtype sets:", {str(k): v for k, v in dt.items()})
    print("   sample contract:", json.dumps(r0.get("contract"))[:700])

fz = Path("/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft.freeze.json")
if fz.is_file():
    d = json.loads(fz.read_text())
    print("\n== c2c3c5 freeze keys:", list(d.keys()))
    for k, v in d.items():
        s = json.dumps(v)
        print("   %s = %s" % (k, s[:400]))

fzc4 = Path("/root/mk_v2/contracts/contracts_c4_draft.freeze.json")
if fzc4.is_file():
    d = json.loads(fzc4.read_text())
    print("\n== c4 freeze keys:", list(d.keys()))
    for k, v in d.items():
        print("   %s = %s" % (k, json.dumps(v)[:400]))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_h15.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_h15.py", timeout=300)
print("\n#### local repo contracts dir")
_remote.run(c, "ls -la /root/mk_v2/contracts/ 2>&1 | head -20; "
               "find / -maxdepth 4 -name 'contracts_c4_draft*' 2>/dev/null", timeout=180)
c.close()
print("\nH15_DONE")
