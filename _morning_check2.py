"""Follow-up: confirm-arm tally, run_error units, oom attribution, P37 cell."""
import _remote

CMD = (
    "grep -h 'confirm' /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log "
    "/root/mk_v2_runs/e1/witness_confirmation/audit_lane1.log | "
    "grep -oE 'status=[a-zA-Z]+' | sort | uniq -c; echo SEP; "
    "grep -h 'control' /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log "
    "/root/mk_v2_runs/e1/witness_confirmation/audit_lane1.log | "
    "grep -oE 'status=[a-zA-Z]+' | sort | uniq -c; echo SEP; "
    "grep -hE 'status=fail|status=None|status=inconclusive' "
    "/root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log "
    "/root/mk_v2_runs/e1/witness_confirmation/audit_lane1.log | grep -E 'control'; echo SEP; "
    "ls /root/mk_v2_runs/e1/witness_confirmation/cells/ | head -5; "
    "ls /root/mk_v2_runs/e1/witness_confirmation/cells/ | wc -l; echo SEP; "
    "cat /root/mk_v2_runs/e1/witness_confirmation/cells/*P37*sync_remove*1* 2>/dev/null | head -c 1500; echo SEP; "
    "/root/miniconda3/bin/python -c \"import json; qs=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
    "d=qs['done']; print([u for u,s in d.items() if s=='run_error']); "
    "print([u for u,s in d.items() if s=='calibrated_heavy_tail'])\"; echo SEP; "
    "grep -hE 'run_error|SIGKILL|exit=-9|oom' /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log | tail -12"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=120, echo=False)
c.close()
print(o)
print("MORNING2_DONE")
