"""Local watcher for the wcfu chain: prints alert lines on key events."""
import time
import traceback

import _remote

POLL_S = 900
MAX_HOURS = 22

CMD = (
    "ls /root/mk_v2_runs/e3_b9_calib/WCFU_DONE "
    "/root/mk_v2_runs/e3_b9_calib/WCFU_BLOCKED "
    "/root/mk_v2_runs/e3_b9_calib/STAGE1_DONE 2>/dev/null; echo MARK; "
    "pgrep -f _wcfu_chain.py | wc -l; "
    "pgrep -f _b9_calib_driver_v2.py | wc -l; echo MARK; "
    "tail -n 3 /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log 2>/dev/null; echo MARK; "
    "/root/miniconda3/bin/python -c \"import json; "
    "qs=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
    "print('wave', qs.get('wave'), 'done', len(qs['done']), "
    "'pending', len(qs['pending']), 'claimed', len(qs.get('claimed', {})))\""
)


def main():
    deadline = time.time() + MAX_HOURS * 3600
    last = ""
    while time.time() < deadline:
        try:
            c = _remote.connect()
            _, o, _ = _remote.run(c, CMD, timeout=90, echo=False)
            c.close()
            print("=== %s ===" % time.strftime("%H:%M:%S"), flush=True)
            print(o, flush=True)
            if "WCFU_BLOCKED" in o:
                print("ALERT_WCFU_BLOCKED", flush=True)
                return
            if "WCFU_DONE" in o:
                print("ALERT_WCFU_DONE", flush=True)
                return
            counts = [l.strip() for l in o.split("MARK")[1].splitlines()
                      if l.strip()]
            if counts and counts[0] == "0":
                print("ALERT_CHAIN_DEAD", flush=True)
                return
            last = o
        except Exception:
            print("WATCH_WARN transient: %s"
                  % traceback.format_exc(limit=1).strip().splitlines()[-1],
                  flush=True)
        time.sleep(POLL_S)
    print("ALERT_WATCH_TIMEOUT", flush=True)


if __name__ == "__main__":
    main()
