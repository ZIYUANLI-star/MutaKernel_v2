"""Probe the two claimed contract gaps (L3 task files, C4 draft) on the remote."""
import io

import _remote

SCRIPT = r'''
import hashlib, json, os
from pathlib import Path

MK = Path("/root/mk_v2")
print("== vendored KernelBench levels ==")
for root in (MK / "KernelBench" / "KernelBench", MK / "KernelBench"):
    if root.is_dir():
        print(" ", root, "->", sorted(p.name for p in root.iterdir() if p.is_dir()))
for lvl in (1, 2, 3, 4):
    d = MK / "KernelBench" / "KernelBench" / ("level%d" % lvl)
    n = len(list(d.glob("*.py"))) if d.is_dir() else None
    print("  level%d: dir=%s py=%s" % (lvl, d.is_dir(), n))

print("== contracts dir ==")
for d in (MK / "contracts", Path("/root/mk_v2_runs/e2"), Path("/root/mk_v2_runs/e3")):
    if d.is_dir():
        for p in sorted(d.rglob("contracts_*")):
            print("  %-70s %10d" % (str(p), p.stat().st_size))

print("== c4 draft anywhere under /root (maxdepth 5) ==")
hits = []
for base in ("/root",):
    for dirpath, dirnames, filenames in os.walk(base):
        depth = dirpath.count("/")
        if depth > 5:
            dirnames[:] = []
            continue
        for fn in filenames:
            if "c4_draft" in fn or "tritonbench" in fn.lower() and fn.endswith(".jsonl"):
                hits.append(os.path.join(dirpath, fn))
for h in hits[:40]:
    try:
        sz = os.path.getsize(h)
    except OSError:
        sz = -1
    print("  %-80s %10d" % (h, sz))
if not hits:
    print("  (none)")

print("== c2c3c5 freeze failures summary ==")
f = MK / "contracts" / "contracts_c2c3c5_draft.freeze.json"
if not f.is_file():
    for cand in Path("/root").rglob("contracts_c2c3c5_draft.freeze.json"):
        f = cand
        break
if f.is_file():
    d = json.loads(f.read_text())
    print("  path:", f)
    print("  contracts:", d.get("contracts"), "failures:", len(d.get("failures", [])))
    print("  batch_sha256:", d.get("batch_sha256"))
    errs = {}
    for row in d.get("failures", []):
        errs.setdefault(row.get("error", "?")[:60], []).append(row.get("task_id"))
    for k, v in errs.items():
        print("   %-62s n=%d e.g. %s" % (k, len(v), v[:4]))

print("== TritonBench-G corpus present? ==")
for p in (MK / "external" / "C4_tritonbench" / "data",):
    print(" ", p, p.is_dir())
    if p.is_dir():
        for q in sorted(p.iterdir())[:10]:
            print("   ", q.name, q.is_dir() and "(dir)" or q.stat().st_size)

print("== KernelBench git provenance (vendored) ==")
for cand in (MK / "KernelBench",):
    print(" ", cand, "git:", (cand / ".git").exists())
    for meta in ("README.md", "pyproject.toml"):
        p = cand / meta
        if p.is_file():
            print("   %s sha256=%s size=%d" % (meta,
                  hashlib.sha256(p.read_bytes()).hexdigest()[:16], p.stat().st_size))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_gap1_probe.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_gap1_probe.py", timeout=600)
c.close()
