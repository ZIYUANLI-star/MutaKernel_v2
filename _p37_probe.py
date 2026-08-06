import _remote

c = _remote.connect()
for cmd in [
    # the 5 P37 records: id/outcome/witness/divergence oracle structure
    "grep -h 'L1_P37__' /root/mk_v2_runs/e1/cse_observations_lane*.jsonl | "
    "/root/miniconda3/bin/python -c \"import sys,json\nfor l in sys.stdin:\n r=json.loads(l)\n d=r.get('divergence') or {}\n print(json.dumps({'id':r['probe_id'],'outcome':r.get('outcome'),'policy':d.get('policy'),'sub':d.get('sub_index'),'seed':d.get('seed'),'detail':d.get('detail'),'oracle':d.get('oracle')},ensure_ascii=False))\"",
    # lane3 progress + trigger still armed
    "tail -2 /root/mk_v2_runs/e1_cse_lane3.log; pgrep -af 'final_window_trigger.sh' | grep -v 'bash -c' ; ls /root/mk_v2_runs/e1/CSE_DONE_LANE3 2>/dev/null || echo LANE3_NOT_DONE_YET",
    # exact policy name in bank
    "grep -n 'boundary_last_element' /root/mk_v2/src/stress/policy_bank.py | head -5",
]:
    print("### " + cmd[:70])
    _remote.run(c, cmd, timeout=60)
c.close()
print("P37_PROBE_DONE")
