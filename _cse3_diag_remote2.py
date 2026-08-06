#!/usr/bin/env python3
"""Forensics pass 2: kernel input sizes, heartbeat series, event context."""
import glob
import json
import os
import re


def cat(p):
    try:
        return open(p, encoding="utf-8").read()
    except Exception as e:
        return f"<{e}>"


print("=== I2. get_inputs sources ===")
for num in (52, 46, 23, 22, 53):
    for h in sorted(glob.glob(f"/root/mk_v2/KernelBench/level1/{num}_*.py")):
        src = cat(h)
        gm = re.search(r"(def get_inputs.*?)(?=\ndef |\Z)", src, re.S)
        head = re.findall(r"^[a-zA-Z_][a-zA-Z_0-9]*\s*=\s*[^\n]+$", src, re.M)
        print(f"-- {os.path.basename(h)} --")
        print("\n".join(head[:8]))
        print(gm.group(1).strip() if gm else "<no get_inputs>")

print("\n=== L. heartbeat around events + latest ===")
hb = "/root/mk_v2_runs/sentinel_heartbeat.jsonl"
lines = [json.loads(x) for x in open(hb, encoding="utf-8") if x.strip()]
print("total heartbeats:", len(lines), "first at:", lines[0].get("at"),
      "last at:", lines[-1].get("at"))
windows = [("2026-07-28T12:2", "2026-07-28T13:3"),
           ("2026-07-29T01:3", "2026-07-29T02:3")]
for h in lines:
    at = str(h.get("at", ""))
    if any(lo <= at <= hi + "\xff" for lo, hi in
           [(w[0], w[1]) for w in windows]) and (
            at.startswith("2026-07-28T12") or at.startswith("2026-07-28T13")
            or at.startswith("2026-07-29T01") or at.startswith("2026-07-29T02")):
        print(json.dumps({k: h.get(k) for k in
                          ("at", "mem_used_gb", "gpu_mem_used_mib",
                           "oom_kill_lines", "actions", "new_oom_kills")},
                         ensure_ascii=False))
print("-- latest 3 --")
for h in lines[-3:]:
    print(json.dumps({k: h.get(k) for k in
                      ("at", "mem_used_gb", "gpu_mem_used_mib",
                       "oom_kill_lines", "actions")}, ensure_ascii=False))

print("\n=== M. lane records around events ===")
for lane, lo, hi in (
        (3, "2026-07-28T12:00", "2026-07-28T14:30"),
        (5, "2026-07-28T12:00", "2026-07-28T14:30"),
        (3, "2026-07-29T00:30", "2026-07-29T03:30"),
        (5, "2026-07-29T00:30", "2026-07-29T03:30")):
    f = f"/root/mk_v2_runs/e1/cse_observations_lane{lane}.jsonl"
    print(f"-- lane{lane} {lo}..{hi} --")
    for line in open(f, encoding="utf-8"):
        r = json.loads(line)
        fin = r.get("finished_at", "")
        if lo <= fin <= hi:
            print(json.dumps({
                "probe": r["probe_id"], "outcome": r.get("outcome"),
                "wall_s": round((r.get("wall_ms") or 0) / 1000),
                "finished_at": fin,
                "rounds": len(r.get("trials") or []),
            }))

print("\n=== N. worker logs for the two new INCs ===")
for pat in ("*P46__relop_replace__5*", "*P23__mask_boundary__1*",
            "*P52__arith_replace__11*"):
    for h in glob.glob(f"/root/mk_v2_runs/e1/worker_logs/{pat}"):
        print(f"-- {os.path.basename(h)} (last 400 chars) --")
        print(cat(h)[-400:])

print("\n=== O. current worker VmHWM/VmRSS ===")
import subprocess
r = subprocess.run("ps -eo pid,args | grep _mutant_worker | grep -v grep",
                   shell=True, capture_output=True, text=True)
for ln in r.stdout.splitlines():
    pid = ln.split()[0]
    st = cat(f"/proc/{pid}/status")
    hwm = re.search(r"VmHWM:\s*(\d+)", st)
    rss = re.search(r"VmRSS:\s*(\d+)", st)
    print(pid, "HWM_GB=", round(int(hwm.group(1)) / 1048576, 1) if hwm else "?",
          "RSS_GB=", round(int(rss.group(1)) / 1048576, 1) if rss else "?",
          ln.split("cfg_")[-1][:50])

print("\n=== P. cgroup memory numbers again ===")
for p in ("memory.limit_in_bytes", "memory.usage_in_bytes",
          "memory.max_usage_in_bytes"):
    v = cat(f"/sys/fs/cgroup/memory/{p}").strip()
    print(p, v, f"({round(int(v)/2**30,1)} GiB)" if v.isdigit() else "")
print("oom_control:", cat("/sys/fs/cgroup/memory/memory.oom_control").strip())

print("\nDIAG2_DONE")
