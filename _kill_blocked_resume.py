"""Terminate the permanently blocked resume_b9.sh shell, by explicit PID only.

Safety properties, all re-verified inside the remote script immediately before
the signal:

  * the target's cmdline must contain resume_b9.sh (never signal a PID whose
    identity we have not just confirmed);
  * only the single PID is signalled -- never its process group.  The target and
    the guard share pgrp/sid inherited from the dead trigger session, so a group
    signal would take the guard down with it;
  * no lane driver may be running (a lane mid-unit would lose that unit);
  * the guard must be alive before and after, and the checkpoint files and the
    cgroup oom_kill counter must be unchanged afterwards.

`pkill -f` / `pgrep -f` are not used anywhere: the pattern would also match the
ssh command line carrying it.  The needle strings for the critical-path scanners
are assembled from fragments so that this file's own name never matches them.
"""
import io

import _remote

SCRIPT = r'''
import json, os, signal, sys, time
from pathlib import Path

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
TARGET_NEEDLE = "resume_b9.sh"
LANE_NEEDLE = "calib_driver_v2.py"
GUARD_NEEDLE = "guard_b9"


def cmdline(pid):
    try:
        return Path("/proc/%d/cmdline" % pid).read_bytes().replace(
            b"\0", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return ""


def ppid_of(pid):
    try:
        for line in open("/proc/%d/status" % pid, encoding="utf-8"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def scan(needle):
    excluded, pid = set(), os.getpid()
    while pid and pid != 1:
        excluded.add(pid)
        pid = ppid_of(pid)
    return [int(e) for e in os.listdir("/proc")
            if e.isdigit() and int(e) not in excluded
            and needle in cmdline(int(e))]


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


def snapshot():
    state = json.loads((OUT / "queue_state.json").read_text())
    completed = {p.name: json.loads(p.read_text())
                 for p in sorted(OUT.glob("completed_v2_lane*.json"))}
    rows = {p.name: len([x for x in p.read_text().splitlines() if x.strip()])
            for p in sorted(OUT.glob("calibration_v2_lane*.jsonl"))}
    return {"pending": sorted(state["pending"]), "claimed": sorted(state["claimed"]),
            "done": len(state["done"]), "completed": completed, "rows": rows,
            "oom": oom()}


print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
lanes = scan(LANE_NEEDLE)
if lanes:
    sys.exit("REFUSING: lane driver(s) alive %s -- a running unit must not be "
             "disturbed" % lanes)
guards_before = scan(GUARD_NEEDLE)
if not guards_before:
    sys.exit("REFUSING: no guard alive; the situation is not the one analysed")
targets = scan(TARGET_NEEDLE)
print("guard before   :", guards_before)
print("targets        :", [(p, cmdline(p)[:90]) for p in targets])
if not targets:
    print("nothing to terminate (already gone)")
    print("KILL_SKIPPED")
    raise SystemExit(0)

before = snapshot()
print("before: pending=%d claimed=%d done=%d rows=%s oom=%s"
      % (len(before["pending"]), len(before["claimed"]), before["done"],
         before["rows"], before["oom"]))

for pid in targets:
    cl = cmdline(pid)
    if TARGET_NEEDLE not in cl:
        print("  skip %d: identity changed under us (%s)" % (pid, cl[:60]))
        continue
    kids = [p for p in os.listdir("/proc")
            if p.isdigit() and ppid_of(int(p)) == pid]
    print("  target %d children=%s (they reparent to init, not die)" % (pid, kids))
    os.kill(pid, signal.SIGTERM)      # single PID, never the process group
    print("  SIGTERM -> %d" % pid)

time.sleep(4)
left = scan(TARGET_NEEDLE)
if left:
    for pid in left:
        if TARGET_NEEDLE in cmdline(pid):
            os.kill(pid, signal.SIGKILL)
            print("  SIGKILL -> %d" % pid)
    time.sleep(3)

print("\n=== verification ===")
after = snapshot()
guards_after = scan(GUARD_NEEDLE)
lanes_after = scan(LANE_NEEDLE)
print("target left    :", scan(TARGET_NEEDLE) or "none")
print("guard after    :", guards_after)
print("guard ppid     :", {p: ppid_of(p) for p in guards_after})
print("lane drivers   :", lanes_after or "none")
print("after: pending=%d claimed=%d done=%d rows=%s oom=%s"
      % (len(after["pending"]), len(after["claimed"]), after["done"],
         after["rows"], after["oom"]))

problems = []
if scan(TARGET_NEEDLE):
    problems.append("target still alive")
if not guards_after:
    problems.append("guard died with the parent")
for key in ("pending", "claimed", "done", "completed", "rows", "oom"):
    if before[key] != after[key]:
        problems.append("%s changed: %r -> %r" % (key, before[key], after[key]))
print("\n" + ("KILL_VERIFIED" if not problems else "KILL_PROBLEMS " + "; ".join(problems)))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_kill_blocked_resume.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_kill_blocked_resume.py",
            timeout=300)
c.close()
