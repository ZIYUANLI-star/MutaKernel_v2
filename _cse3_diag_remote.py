#!/usr/bin/env python3
"""Remote forensics for the 3 same-signature INCONCLUSIVEs (2026-07-29)."""
import glob
import json
import os
import re
import subprocess


BASE = "/root/mk_v2_runs/e1"


def sh(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        return (r.stdout + r.stderr).rstrip()
    except Exception as e:
        return f"<cmd failed: {e}>"


print("=== A. processes (drivers/workers/guard, rss KB) ===")
print(sh("ps -eo pid,ppid,etimes,rss,args --sort=pid | "
         "grep -E 'run_e1_cse_falsify|_mutant_worker|guard_cse' | grep -v grep"))

print("\n=== B. host memory / cgroup ===")
print(sh("free -g"))
for pid in ("146300", "164619"):
    print(f"cgroup of {pid}:", sh(f"cat /proc/{pid}/cgroup 2>/dev/null"))
print("v2 max/current/peak:",
      sh("cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.current "
         "/sys/fs/cgroup/memory.peak 2>/dev/null"))
print("v2 memory.events:", sh("cat /sys/fs/cgroup/memory.events 2>/dev/null"))
print("v1 limit/usage/max_usage:",
      sh("cat /sys/fs/cgroup/memory/memory.limit_in_bytes "
         "/sys/fs/cgroup/memory/memory.usage_in_bytes "
         "/sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null"))
print("v1 oom_control:", sh("cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null"))
print("v1 failcnt:", sh("cat /sys/fs/cgroup/memory/memory.failcnt 2>/dev/null"))

print("\n=== C. kernel oom traces ===")
print(sh("dmesg -T 2>/dev/null | grep -iE 'oom|out of memory|killed process' | tail -50"))
print("-- journalctl --")
print(sh("journalctl -k --since '2026-07-28 10:00' 2>/dev/null | "
         "grep -iE 'oom|killed process' | tail -50"))

print("\n=== D. all INCONCLUSIVE records in lane obs ===")
for f in sorted(glob.glob(BASE + "/cse_observations_lane*.jsonl")):
    for line in open(f, encoding="utf-8"):
        r = json.loads(line)
        if r.get("outcome") != "INCONCLUSIVE":
            continue
        tr = r.get("trials") or []
        last = [
            {k: t.get(k) for k in
             ("round_type", "policy", "sub_index", "round_index", "status")}
            for t in tr[-3:]
        ]
        print(json.dumps({
            "file": os.path.basename(f),
            "probe": r["probe_id"],
            "kernel": r.get("kernel"),
            "wall_s": round((r.get("wall_ms") or 0) / 1000),
            "finished_at": r.get("finished_at"),
            "valid_rounds": r.get("valid_rounds"),
            "rounds": len(tr),
            "class": r.get("inconclusive_class"),
            "pipeline": r.get("input_pipeline"),
            "timed_out": r.get("timed_out"),
            "last_trials": last,
        }, ensure_ascii=False))

print("\n=== E. obs record count + last record per lane ===")
for f in sorted(glob.glob(BASE + "/cse_observations_lane*.jsonl")):
    lines = open(f, encoding="utf-8").read().splitlines()
    lastr = json.loads(lines[-1]) if lines else {}
    print(os.path.basename(f), "n=", len(lines), "last=",
          lastr.get("probe_id"), lastr.get("outcome"),
          "wall_s=", round((lastr.get("wall_ms") or 0) / 1000),
          lastr.get("finished_at"))

print("\n=== F. lane log tails ===")
for lane in (3, 5):
    print(f"-- e1_cse_lane{lane}.log tail --")
    print(sh(f"tail -n 25 /root/mk_v2_runs/e1_cse_lane{lane}.log"))

print("\n=== G. sentinel heartbeat tail ===")
print(sh(f"tail -n 5 {BASE}/sentinel_heartbeat.jsonl 2>/dev/null || "
         "find /root/mk_v2_runs -name sentinel_heartbeat.jsonl | head"))

print("\n=== H. driver cmdlines ===")
for pid in ("146300", "164619"):
    print(pid, sh(f"tr '\\0' ' ' < /proc/{pid}/cmdline 2>/dev/null"))

print("\n=== I. get_inputs of P52/P46/P23/P22/P53 ===")
kb = None
cmdline = sh("tr '\\0' ' ' < /proc/146300/cmdline 2>/dev/null")
m = re.search(r"--kernelbench-root\s+(\S+)", cmdline)
if m:
    kb = m.group(1)
print("kb root:", kb)
if kb:
    for pid_num in (52, 46, 23, 22, 53):
        hits = glob.glob(os.path.join(kb, "level1", f"{pid_num}_*.py"))
        for h in hits:
            src = open(h, encoding="utf-8").read()
            gm = re.search(r"(def get_inputs.*?)(?=\ndef |\Z)", src, re.S)
            im = re.search(r"(def get_init_inputs.*?)(?=\ndef |\Z)", src, re.S)
            print(f"-- {os.path.basename(h)} --")
            print(gm.group(1).strip() if gm else "<no get_inputs>")
            if im:
                print(im.group(1).strip()[:300])

print("\n=== J. lane5 manifest input_pipeline / start ===")
for f in sorted(glob.glob(BASE + "/cse_run_manifest_lane5*.json")):
    mj = json.loads(open(f, encoding="utf-8").read())
    print(os.path.basename(f), mj.get("started_at"), mj.get("run_id"))
    print("  input_pipeline:", (mj.get("input_pipeline") or "")[:80])
    print("  policy_skip:", mj.get("policy_skip"))

print("\n=== K. guard log tail ===")
print(sh("ls -la /root/mk_v2_runs/e1_guard* 2>/dev/null | head; "
         "tail -n 15 /root/mk_v2_runs/e1_guard_cse_split.log 2>/dev/null"))

print("\nDIAG_DONE")
