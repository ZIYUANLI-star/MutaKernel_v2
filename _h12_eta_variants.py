"""ETA for every scope option, using the deployed simulate() so numbers match."""
import io

import _remote

SCRIPT = r'''
import json, sys, collections
sys.path.insert(0, "/root/mk_v2")
import _b9_resume_prep as prep

kept, requeued, fresh, queue = prep.build("table")
print("kept=%d requeued=%d fresh=%d queue=%d" % (len(kept), len(requeued), len(fresh), len(queue)))

def h(s):
    return "%.1f h / %.2f d" % (s / 3600.0, s / 86400.0)

def eta(subset, lanes=2, budget=100.0):
    f = prep.simulate(subset, lanes, budget, "est_wall_s_fast")
    s = prep.simulate(subset, lanes, budget, "est_wall_s_slow")
    return f, s

variants = [
    ("A. full remaining queue (382 units)", queue),
    ("B. reduction_heavy units only", [u for u in queue if u["reduction_heavy"]]),
    ("C. non-reduction units only", [u for u in queue if not u["reduction_heavy"]]),
    ("D. reserve < 60 GiB (drop the big tail)", [u for u in queue if u["reserve_gb"] < 60]),
    ("E. reserve < 90 GiB (drop only the over-budget units)",
     [u for u in queue if u["reserve_gb"] < 90]),
    ("F. reserve >= 60 GiB (the tail alone)", [u for u in queue if u["reserve_gb"] >= 60]),
    ("G. reserve >= 90 GiB (over-budget, strictly serial)",
     [u for u in queue if u["reserve_gb"] >= 90]),
    ("H. first wave: the 13 requeued units", requeued),
    ("I. float32 units only", [u for u in queue if u["dtype"] == "float32"]),
    ("J. L1 tasks only", [u for u in queue if u["task_key"].startswith("L1_")]),
    ("K. L2 tasks only", [u for u in queue if u["task_key"].startswith("L2_")]),
]
print("\n%-52s %5s   %-22s %-22s" % ("variant", "units", "2 lanes fast..slow", "1 lane fast..slow"))
for label, subset in variants:
    if not subset:
        print("%-52s %5d   (empty)" % (label, 0))
        continue
    f2, s2 = eta(subset, 2)
    f1, s1 = eta(subset, 1)
    print("%-52s %5d   %-22s %-22s"
          % (label, len(subset), "%s .. %s" % (h(f2), h(s2)), "%s .. %s" % (h(f1), h(s1))))

print("\n== ascending-size order (graceful degradation) for the full queue")
for order in ("table", "asc", "desc"):
    _k, _r, _f, q = prep.build(order)
    f2, s2 = eta(q, 2)
    print("   order=%-6s 2 lanes: %s .. %s" % (order, h(f2), h(s2)))

print("\n== where the cost sits (2-lane fast/slow contribution by size band)")
bands = [(0, 15), (15, 30), (30, 60), (60, 90), (90, 1e9)]
tot_f = sum(u["est_wall_s_fast"] for u in queue)
tot_s = sum(u["est_wall_s_slow"] for u in queue)
print("   total serial work: fast %s, slow %s" % (h(tot_f), h(tot_s)))
for lo, hi in bands:
    m = [u for u in queue if lo <= u["reserve_gb"] < hi]
    if not m:
        continue
    f = sum(u["est_wall_s_fast"] for u in m)
    s = sum(u["est_wall_s_slow"] for u in m)
    print("   reserve [%3g,%4g) GiB: %3d units  fast %5.1f h (%4.1f%%)  slow %6.1f h (%4.1f%%)"
          % (lo, hi, len(m), f / 3600, 100 * f / tot_f, s / 3600, 100 * s / tot_s))

print("\n== the 20 most expensive units (slow model) and what they are")
big = sorted(queue, key=lambda u: -u["est_wall_s_slow"])[:20]
for u in big:
    print("   %-22s reserve=%6.1f GiB in=%.3e out=%.3e fast=%5.1fh slow=%5.1fh  %s"
          % (u["unit"], u["reserve_gb"], u["in_numel"], u["out_numel"],
             u["est_wall_s_fast"] / 3600, u["est_wall_s_slow"] / 3600,
             u["task_file"].split("/")[-1]))

print("\n== reduction_heavy flag: how was it set? distribution over task files")
tt = json.loads(open("/root/mk_v2_runs/e3_b9_calib/task_table.json").read())
nonrh = [t for t in tt["tasks"] if not t["reduction_heavy"]]
print("   NON reduction_heavy tasks (%d):" % len(nonrh))
for t in nonrh:
    print("     %-10s %s" % (t["task_key"], t["file"].split("/")[-1]))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_h12.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_h12.py", timeout=600)
print("\n#### reduction_heavy definition in the builder")
_remote.run(c, "grep -rn 'reduction_heavy' /root/mk_v2/_b9*.py /root/mk_v2/scripts/*.py 2>/dev/null | head -20", timeout=180)
c.close()
print("\nH12_DONE")
