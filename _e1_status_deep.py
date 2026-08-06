import json
import _remote

c = _remote.connect()
cmd = (
    "tail -c 3000 /root/mk_v2_runs/e1_baseline.log; echo __SEP__; "
    "wc -l < /root/mk_v2_runs/e1/baseline_observations.jsonl 2>/dev/null; echo __SEP__; "
    "cat /root/mk_v2_runs/e1/original_controls.json 2>/dev/null; echo __SEP__; "
    "tail -n 400 /root/mk_v2_runs/e1/baseline_observations.jsonl 2>/dev/null | "
    "python3 -c \"import sys,json,collections; "
    "recs=[json.loads(l) for l in sys.stdin if l.strip()]; "
    "st=collections.Counter(r.get('status') for r in recs); "
    "lv=collections.Counter((r.get('level'), r.get('status')) for r in recs); "
    "print(json.dumps({'status': dict(st), 'by_level': {f'{k[0]}|{k[1]}': v for k,v in lv.items()}}))\"; "
    "echo __SEP__; "
    "ps aux | grep 'run_e1_probe_[s]tudy' | head -3; echo __SEP__; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; echo __SEP__; "
    "grep -ciE 'traceback|error' /root/mk_v2_runs/e1_baseline.log"
)
_, out, _ = _remote.run(c, cmd, timeout=180, echo=False)
c.close()

parts = out.split("__SEP__")
labels = ["LOG_TAIL", "OBS_COUNT", "CONTROLS", "RECENT_STATUS", "PROC", "GPU", "LOG_ERR_LINES"]
for lab, p in zip(labels, parts):
    print(f"===== {lab} =====")
    print(p.strip()[:3500])
print("DEEP_DONE")
