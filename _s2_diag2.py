"""Read guard log tail + full guard script to see why no driver launches."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "echo ===LOG_TAIL===; tail -25 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log; "
    "echo ===SCRIPT===; cat /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.sh; "
    "echo ===CLAIMED===; /root/miniconda3/bin/python -c \"import json; "
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
    "print(json.dumps(q['claimed'], indent=1)[:1500])\""),
    timeout=60, echo=False)
print(o)
c.close()
