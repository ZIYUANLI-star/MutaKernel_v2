"""Morning sweep: WC completion + report, B9 stage1 status, system health."""
import _remote

CMD1 = (
    "date '+NOW=%F %T %z'; echo SEP; "
    "ls -la /root/mk_v2_runs/e1/witness_confirmation/ | grep -iE 'STAGE_DONE|report|jsonl'; echo SEP; "
    "tail -n 25 /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log; echo SEP; "
    "tail -n 25 /root/mk_v2_runs/e1/witness_confirmation/audit_lane1.log; echo SEP; "
    "ps aux | grep -E '_wc|_mutant_worker|_b9|guard|falsify' | grep -v grep; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader"
)

CMD2 = (
    "tail -c 3000 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log; echo SEP; "
    "ls /root/mk_v2_runs/e3_b9_calib/ | grep -iE 'STAGE1|GATE|EXIT|FIRED|PAUSED'; "
    "cat /root/mk_v2_runs/e3_b9_calib/STAGE1_GATE_REPORT.json 2>/dev/null | head -c 2500; echo SEP; "
    "for f in /root/mk_v2_runs/e3_b9_calib/lane_v2_*.log; do echo \"== $f\"; tail -n 6 $f; done; echo SEP; "
    "/root/miniconda3/bin/python -c \"import json; qs=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
    "print('wave', qs.get('wave')); print('pending', len(qs.get('pending', []))); print('claimed', qs.get('claimed')); "
    "d=qs.get('done', {}); print('done', len(d)); "
    "from collections import Counter; print(dict(Counter(d.values())))\"; echo SEP; "
    "for p in /sys/fs/cgroup/memory/memory.oom_control; do grep -H oom_kill $p; done; "
    "tail -c 400 /root/mk_v2_runs/e1_sentinel.log"
)

c = _remote.connect()
print("##### WC #####")
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print("##### B9 / SYSTEM #####")
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
c.close()
print(o)
print("MORNING_DONE")
