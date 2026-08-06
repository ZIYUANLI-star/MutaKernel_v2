import time
import _remote

c = _remote.connect()
time.sleep(45)  # give the resumed driver time to pass its first control
_, out, _ = _remote.run(c, (
    "/root/miniconda3/bin/python -c \"import json; "
    "print('checkpoint entries:', len(json.load(open('/root/mk_v2_runs/e1/baseline_completed.json'))))\"; echo SEP; "
    "tail -c 700 /root/mk_v2_runs/e1_baseline.log; echo SEP; "
    "wc -l < /root/mk_v2_runs/e1/baseline_observations.jsonl; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"
), timeout=90, echo=False)
c.close()
print(out)
print("VERIFY2_DONE")
