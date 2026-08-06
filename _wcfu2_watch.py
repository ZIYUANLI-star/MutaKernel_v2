"""Local watcher for the wcfu2 control top-up chain."""
import time
import traceback

import _remote

POLL_S = 600
MAX_HOURS = 6

CMD = (
    "ls /root/mk_v2_runs/e3_b9_calib/WCFU2_DONE "
    "/root/mk_v2_runs/e3_b9_calib/WCFU2_BLOCKED 2>/dev/null; echo MARK; "
    "pgrep -f '[_]wcfu2_chain.py' | wc -l; echo MARK; "
    "tail -n 2 /root/mk_v2_runs/e3_b9_calib/wcfu2_chain.log 2>/dev/null"
)


def main():
    deadline = time.time() + MAX_HOURS * 3600
    while time.time() < deadline:
        try:
            c = _remote.connect()
            _, o, _ = _remote.run(c, CMD, timeout=90, echo=False)
            c.close()
            print("=== %s ===" % time.strftime("%H:%M:%S"), flush=True)
            print(o, flush=True)
            if "WCFU2_BLOCKED" in o:
                print("ALERT_WCFU2_BLOCKED", flush=True)
                return
            if "WCFU2_DONE" in o:
                print("ALERT_WCFU2_DONE", flush=True)
                return
            counts = [l.strip() for l in o.split("MARK")[1].splitlines()
                      if l.strip()]
            if counts and counts[0] == "0":
                print("ALERT_WCFU2_CHAIN_DEAD", flush=True)
                return
        except Exception:
            print("WATCH_WARN: %s"
                  % traceback.format_exc(limit=1).strip().splitlines()[-1],
                  flush=True)
        time.sleep(POLL_S)
    print("ALERT_WCFU2_WATCH_TIMEOUT", flush=True)


if __name__ == "__main__":
    main()
