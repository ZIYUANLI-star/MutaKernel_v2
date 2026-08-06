"""Deploy _wc_analyze.py to the remote box and run it.

The analyzer is read-only w.r.t. the E1 ledger, so it is safe to run while the
audit lanes are still in flight; the report it writes is simply a snapshot of
the evidence accumulated so far.
"""
import sys
import time

import _remote

REMOTE_PY = "/root/miniconda3/bin/python"
DEST = "/root/mk_v2/_wc_analyze.py"
WC = "/root/mk_v2_runs/e1/witness_confirmation"


def connect_with_retry(tries=5):
    delays = [20, 40, 60, 90]
    last = None
    for i in range(tries):
        try:
            return _remote.connect()
        except Exception as exc:  # noqa: BLE001
            last = exc
            print("connect attempt %d failed: %s" % (i + 1, exc))
            if i < tries - 1:
                time.sleep(delays[min(i, len(delays) - 1)])
    raise SystemExit("all connect attempts failed: %s" % last)


def main():
    c = connect_with_retry()

    sftp = c.open_sftp()
    sftp.put("_wc_analyze.py", DEST)
    sftp.close()
    print("uploaded -> %s" % DEST)

    print("\n=== lane completion markers ===")
    _remote.run(c, "ls %s/ | grep STAGE_DONE || echo 'none yet'" % WC, timeout=60)
    print("\n=== lane1 progress ===")
    _remote.run(c, "tail -3 %s/audit_lane1.log" % WC, timeout=60)

    print("\n=== analyze ===")
    code, out, _ = _remote.run(
        c, "cd /root/mk_v2 && %s -u _wc_analyze.py 2>&1" % REMOTE_PY, timeout=900)
    c.close()
    sys.exit(0 if code == 0 else 1)


if __name__ == "__main__":
    main()
