"""Dependency check before terminating the blocked resume script.

Read-only.  Establishes: the process tree, whether the guard/lanes are children
that would be affected, who maintains queue_state.json, and what the checkpoint
files currently hold.  Also locates the E2 collection frames and the existing
contract digests needed for the L3 re-extraction regression gate.
"""
import io

import _remote

SCRIPT = r'''
import hashlib, json, os, time
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
MK = Path("/root/mk_v2")
NEEDLES = ["resume_b9", "guard_b9", "calib_driver_v2", "chain_trigger",
           "stage1_chain", "mutant_" + "worker", "cse_falsify", "signoff_" + "orch"]


def read(pid, name):
    try:
        return Path("/proc/%d/%s" % (pid, name)).read_text(errors="replace")
    except OSError:
        return ""


def info(pid):
    ppid, pgrp, sid, state = 0, 0, 0, "?"
    for line in read(pid, "status").splitlines():
        if line.startswith("PPid:"):
            ppid = int(line.split()[1])
        elif line.startswith("State:"):
            state = line.split(None, 1)[1].strip()
    stat = read(pid, "stat").split()
    if len(stat) > 5:
        pgrp, sid = int(stat[4]), int(stat[5])
    cl = read(pid, "cmdline").replace("\0", " ").strip()
    return ppid, pgrp, sid, state, cl


def scan():
    excluded, pid = set(), os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        for line in read(pid, "status").splitlines():
            if line.startswith("PPid:"):
                pid = int(line.split()[1])
                break
        else:
            break
    hits = []
    for e in os.listdir("/proc"):
        if not e.isdigit() or int(e) in excluded:
            continue
        pid = int(e)
        ppid, pgrp, sid, state, cl = info(pid)
        if any(n in cl for n in NEEDLES):
            hits.append((pid, ppid, pgrp, sid, state, cl))
    return sorted(hits)


print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
print("[process tree of interest]")
print("  %-7s %-7s %-7s %-7s %-14s %s"
      % ("pid", "ppid", "pgrp", "sid", "state", "cmdline"))
for pid, ppid, pgrp, sid, state, cl in scan():
    print("  %-7d %-7d %-7d %-7d %-14s %s" % (pid, ppid, pgrp, sid, state, cl[:110]))

print("\n[what the blocked shell is waiting on]")
for pid, ppid, pgrp, sid, state, cl in scan():
    if "resume_b9" in cl:
        print("  pid=%d wchan=%s" % (pid, read(pid, "wchan").strip() or "?"))
        fd = Path("/proc/%d/fd" % pid)
        try:
            for f in sorted(fd.iterdir(), key=lambda p: int(p.name)):
                try:
                    print("    fd %-3s -> %s" % (f.name, os.readlink(str(f))))
                except OSError:
                    pass
        except OSError as exc:
            print("    (fd listing unavailable: %s)" % exc)
        kids = [p for p, pp, _, _, _, c in scan() if pp == pid]
        print("  direct children: %s" % kids)

print("\n[guard fd table: does it hold the parent's pipes?]")
for pid, ppid, pgrp, sid, state, cl in scan():
    if "guard_b9" in cl:
        fd = Path("/proc/%d/fd" % pid)
        links = []
        try:
            for f in sorted(fd.iterdir(), key=lambda p: int(p.name)):
                try:
                    links.append("%s->%s" % (f.name, os.readlink(str(f))))
                except OSError:
                    pass
        except OSError:
            pass
        print("  guard pid=%d ppid=%d fds: %s" % (pid, ppid, " ".join(links)))

print("\n[checkpoint integrity]")
st = json.loads((OUT / "queue_state.json").read_text())
print("  queue_state.json: pending=%d claimed=%d done=%d units=%d wave=%s"
      % (len(st["pending"]), len(st["claimed"]), len(st["done"]),
         len(st["units"]), st.get("wave")))
print("  pending:", st["pending"])
for p in sorted(OUT.glob("completed_v2_lane*.json")):
    print("  %s -> %s" % (p.name, json.loads(p.read_text())))
rows = 0
for p in sorted(OUT.glob("calibration_v2_lane*.jsonl")):
    n = len([x for x in p.read_text().splitlines() if x.strip()])
    rows += n
    print("  %s -> %d rows" % (p.name, n))
print("  total v2 rows: %d" % rows)


def oom():
    for p in ("/sys/fs/cgroup/memory.events",
              "/sys/fs/cgroup/memory/memory.oom_control"):
        try:
            for line in open(p, encoding="utf-8"):
                if line.startswith("oom_kill "):
                    return int(line.split()[1])
        except OSError:
            continue
    return None


print("  oom_kill: %s (baseline 20)" % oom())

print("\n[E2 collection frames + existing contract digests]")
for base in (Path("/root/mk_v2_runs/e2_reconcile"), Path("/root/mk_v2_runs/e2"),
             MK):
    if base.is_dir():
        for p in sorted(base.glob("*collection_frame*")):
            print("  frame: %-70s %d" % (str(p), p.stat().st_size))
old = Path("/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft.jsonl")
print("  old draft: %s exists=%s" % (old, old.is_file()))
if old.is_file():
    rows = [json.loads(l) for l in old.read_text().splitlines() if l.strip()]
    print("  rows=%d  file sha256=%s"
          % (len(rows), hashlib.sha256(old.read_bytes()).hexdigest()))
    digest = {r["task_id"]: r["contract_sha256"] for r in rows}
    Path("/root/_c2c3c5_old_digests.json").write_text(json.dumps(digest, indent=2,
                                                                sort_keys=True))
    print("  wrote /root/_c2c3c5_old_digests.json (%d task_ids)" % len(digest))
    lv = {}
    for t in digest:
        lv[t.split("_")[0]] = lv.get(t.split("_")[0], 0) + 1
    print("  by level:", lv)

print("\n[guard restart command line semantics]")
g = OUT / "guard_b9_v2.sh"
for line in g.read_text().splitlines():
    if "calib_driver_v2" in line or "budget-gb" in line or "LANES=" in line \
            or "BUDGET_GB=" in line:
        print("   ", line.strip()[:150])
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_dep_check.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_dep_check.py", timeout=600)
c.close()
