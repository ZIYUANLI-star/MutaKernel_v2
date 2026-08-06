"""Watch the remote requeue_final run until RQ7_DONE / RQ7_BLOCKED."""
import time
import _remote

POLL_S = 180
MAX_H = 8

start = time.time()
last_log = ""
while time.time() - start < MAX_H * 3600:
    try:
        c = _remote.connect()
        _, o, _ = _remote.run(c, (
            "ls /root/mk_v2_runs/e1/requeue_final/RQ7_DONE "
            "/root/mk_v2_runs/e1/requeue_final/RQ7_BLOCKED 2>/dev/null; "
            "echo ---; tail -3 /root/mk_v2_runs/e1/requeue_final/run.log; "
            "echo ---; pgrep -c -f '[_]rq7_requeue.py'"),
            timeout=60, echo=False)
        c.close()
        if "RQ7_BLOCKED" in o:
            print("RQ7_WATCH: BLOCKED detected")
            print(o)
            break
        if "RQ7_DONE" in o:
            print("RQ7_WATCH: DONE detected")
            print(o)
            break
        tail = o.split("---")[1].strip() if "---" in o else o
        if tail != last_log:
            last_log = tail
            print("[%dmin] %s" % ((time.time() - start) / 60,
                                  tail.splitlines()[-1] if tail else "(no log)"),
                  flush=True)
        alive = o.strip().splitlines()[-1] if o.strip() else "0"
        if alive == "0" and "RQ7_DONE" not in o:
            print("RQ7_WATCH: process gone without DONE marker - STALLED?")
            print(o)
            break
    except Exception as exc:
        print("watch error: %r" % exc, flush=True)
    time.sleep(POLL_S)
else:
    print("RQ7_WATCH: TIMEOUT after %dh" % MAX_H)
