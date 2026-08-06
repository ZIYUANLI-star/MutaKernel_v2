import _remote

PY = r'''
import json, os
base = "/root/mk_v2_runs/e1/"
p = base + "cse_observations_lane3_signoff_requeue.jsonl"
print("=== signoff_requeue results so far ===")
if os.path.exists(p):
    for line in open(p, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        trials = r.get("trials") or []
        nonpass = [t for t in trials
                   if t.get("status") not in ("pass", "passed", "ok")]
        print(f"{r['probe_id']:38s} {r.get('outcome'):26s} "
              f"valid_rounds={r.get('valid_rounds')} "
              f"wall={round((r.get('wall_ms') or 0)/1000)}s "
              f"timed_out={r.get('timed_out')} "
              f"skipped={r.get('skipped_policies')} "
              f"planned={r.get('stress_rounds_planned')}")
        for t in nonpass[:4]:
            print("   nonpass:", json.dumps(
                {k: t.get(k) for k in
                 ("policy", "sub_index", "seed", "status", "reason")},
                ensure_ascii=False)[:220])
else:
    print("no records yet")
print()
print("=== oom / gpu ===")
os.system("grep oom_kill /sys/fs/cgroup/memory.events 2>/dev/null || "
          "grep oom_kill /sys/fs/cgroup/memory/memory.oom_control")
os.system("nvidia-smi --query-gpu=memory.used --format=csv,noheader")
'''

c = _remote.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_signoff_progress_remote.py", "w") as f:
    f.write(PY)
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python -u /root/mk_v2/_signoff_progress_remote.py",
            timeout=120)
c.close()
