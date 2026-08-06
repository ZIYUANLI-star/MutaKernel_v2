"""Run the six-source merge, then regenerate the CSE lane plan against the
merged LIKELY set (deduped)."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_e1_cse_plan_remote.py", "/root/mk_v2/_e1_cse_plan_remote.py")
sftp.close()

print("===== final requeue tail (last 10 L1_P96) =====")
_remote.run(c, "tail -n 3 /root/mk_v2_runs/e1_equiv_lane4_requeue.log", timeout=30)
print("===== SIX-SOURCE MERGE =====")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _e1_merge_lanes_remote.py", timeout=300)
print("===== merged file sanity =====")
_remote.run(c, "wc -l /root/mk_v2_runs/e1/equiv_observations.jsonl; "
               "/root/miniconda3/bin/python -c \"import json; "
               "print('completed:', len(json.load(open('/root/mk_v2_runs/e1/equiv_completed.json'))))\"",
            timeout=30)
print("===== CSE plan (final, vs merged LIKELY) =====")
_remote.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python _e1_cse_plan_remote.py", timeout=300)
c.close()
print("MERGE_AND_PLAN_DONE")
