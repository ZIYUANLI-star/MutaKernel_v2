"""Audit probe 3: failure-log timestamps, guard logic, S1 clean-tree assert."""
import _remote as R

c = R.connect()
print("### lane_m_run.log mtime + guard log")
R.run(c, "stat -c '%y %n' /root/mk_v2_runs/e3_campaign/lane_m_run.log; "
         "ls -la /root/mk_v2_ops/guard_lane_m.sh /root/mk_v2_runs/e3_campaign/guard*.log 2>/dev/null", timeout=60)
print("### guard_lane_m.sh content")
R.run(c, "cat /root/mk_v2_ops/guard_lane_m.sh 2>/dev/null || find /root -maxdepth 3 -name 'guard_lane_m.sh' 2>/dev/null", timeout=60)
print("### guard log tail")
R.run(c, "tail -20 /root/mk_v2_runs/e3_campaign/guard_lane_m.log 2>/dev/null", timeout=60)
print("### s1_freeze body in wave15 orchestrator")
R.run(c, "sed -n '/def s1_freeze/,/def s2_lane_d/p' /root/mk_v2_ops/wave15_orchestrator.py", timeout=60)
print("### obs growth check")
R.run(c, "wc -l /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl; "
         "tail -1 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | "
         "/root/miniconda3/bin/python -c \"import sys,json; r=json.loads(sys.stdin.read()); "
         "print({k:r.get(k) for k in ('case_id','subject_id','status','strategy')})\"", timeout=60)
c.close()
print("AUDIT3_DONE")
