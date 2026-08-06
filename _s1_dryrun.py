"""Read-only: resume-prep dry run + the stage split by reservation size."""
import io

import _remote

SCRIPT = r'''
import json, sys
sys.path.insert(0, "/root/mk_v2")
import _b9_resume_prep as prep

kept, requeued, fresh, queue = prep.build("table")
big = [u for u in queue if u["reserve_gb"] >= 60.0]
small = [u for u in queue if u["reserve_gb"] < 60.0]
print("kept=%d requeued=%d fresh=%d queue=%d" % (len(kept), len(requeued),
                                                 len(fresh), len(queue)))
print("stage1 (<60 GiB reserve) = %d ; stage2 (>=60 GiB) = %d" % (len(small), len(big)))
fw = [u["unit"] for u in requeued]
print("first wave (%d): %s" % (len(fw), fw))
print("first-wave units with reserve>=60: %s"
      % [u["unit"] for u in requeued if u["reserve_gb"] >= 60.0])
print()
hdr = "%-24s %-16s %11s %9s %9s %8s %7s %7s"
print(hdr % ("unit", "prev_status", "out_numel", "est_peak", "reserve",
             "timeout", "fast_s", "slow_s"))
for u in requeued:
    print(hdr % (u["unit"], u["previous_status"], "%.4g" % u["out_numel"],
                 "%.1f GB" % u["est_peak_gb"], "%.1f GiB" % u["reserve_gb"],
                 "%ds" % u["unit_timeout_s"], u["est_wall_s_fast"],
                 u["est_wall_s_slow"]))
print()
for label, subset in (("first wave (13)", requeued), ("stage 1 (<60GiB)", small),
                      ("stage 2 (>=60GiB)", big), ("whole queue", queue)):
    for lanes in (1, 2):
        f = prep.simulate(subset, lanes, 100.0, "est_wall_s_fast")
        s = prep.simulate(subset, lanes, 100.0, "est_wall_s_slow")
        print("%-18s %d lane: %7.2f h .. %8.2f h" % (label, lanes, f / 3600, s / 3600))
print()
print("== stage-1 reservation histogram")
import collections
h = collections.Counter()
for u in small:
    for lo, hi in ((0, 5), (5, 15), (15, 30), (30, 45), (45, 60)):
        if lo <= u["reserve_gb"] < hi:
            h["[%d,%d)" % (lo, hi)] += 1
for k in sorted(h, key=lambda x: int(x.strip("[)").split(",")[0])):
    print("   %-10s %d" % (k, h[k]))
json.dump({"stage1": [u["unit"] for u in small],
           "stage2": [u["unit"] for u in big],
           "first_wave": fw},
          open("/root/_s1_stage_sets.json", "w"), indent=2)
print("wrote /root/_s1_stage_sets.json")
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_s1_dryrun.py")
sftp.close()
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python /root/_s1_dryrun.py",
            timeout=600)
c.close()
