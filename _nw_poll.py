"""Poll the remote box for review progress until the review finishes."""
import time

import _remote

CMD = r"""
cd /root/mk_v2_runs/e1/final_window_review/p37_sync_remove_1_newwitness 2>/dev/null || exit 9
S=$(python3 -c "import json;print(json.load(open('STATUS.json'))['state'])" 2>/dev/null)
D=$(ls /root/mk_v2_runs/e1/SIGNOFF_ORCH_DONE >/dev/null 2>&1 && echo yes || echo no)
G=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader)
N=$(ls *_result.json 2>/dev/null | wc -l)
echo "STATE=$S SIGNOFF_DONE=$D results=$N gpu=$G"
tail -2 review.log
if [ -f review_summary.json ]; then echo REVIEW_DONE; fi
"""

while True:
    try:
        c = _remote.connect()
        _, out, _ = _remote.run(c, CMD, timeout=180, echo=False)
        c.close()
        print("[%s] %s" % (time.strftime("%H:%M:%S"), out.strip().replace("\n", " | ")),
              flush=True)
        if "REVIEW_DONE" in out:
            print("REVIEW_FINISHED", flush=True)
            break
    except Exception as exc:
        print("[%s] poll error: %s" % (time.strftime("%H:%M:%S"), exc), flush=True)
    time.sleep(150)
