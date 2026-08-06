"""Deploy the WC-1 analyzer to the remote box and run it.

Usage:  python _wc_finish.py [--wait]

--wait first blocks until lane1 writes STAGE_DONE_all_lane1 (lane0 is already
done), polling every 3 minutes, then runs the analysis.
"""
import sys
import time

import _remote

PY = "/root/miniconda3/bin/python"
WC = "/root/mk_v2_runs/e1/witness_confirmation"
LOCAL = "_wc_analyze.py"
REMOTE = "/root/mk_v2/_wc_analyze.py"


def connect_retry(tries=5):
    delays = [20, 40, 60, 90, 120]
    last = None
    for i in range(tries):
        try:
            return _remote.connect()
        except Exception as exc:  # noqa: BLE001
            last = exc
            print("connect attempt %d failed: %s" % (i + 1, exc), flush=True)
            time.sleep(delays[min(i, len(delays) - 1)])
    raise SystemExit("all connect attempts failed: %s" % last)


def deploy(c):
    sftp = c.open_sftp()
    sftp.put(LOCAL, REMOTE)
    sftp.close()
    _remote.run(c, "md5sum %s" % REMOTE, timeout=60)


def lane_state(c):
    _, out, _ = c.exec_command("ls %s/ | grep -c STAGE_DONE_all_ ; "
                               "tail -2 %s/audit_lane1.log" % (WC, WC))
    return out.read().decode(errors="replace")


def main():
    wait = "--wait" in sys.argv
    c = connect_retry()
    print("=== deploy analyzer ===")
    deploy(c)

    if wait:
        for poll in range(120):          # up to 6 h
            try:
                txt = lane_state(c)
            except Exception as exc:  # noqa: BLE001
                print("poll failed (%s); reconnecting" % exc, flush=True)
                try:
                    c.close()
                except Exception:  # noqa: BLE001
                    pass
                c = connect_retry()
                continue
            n_done = txt.strip().splitlines()[0].strip()
            print("[poll %d] STAGE_DONE_all count=%s\n%s"
                  % (poll, n_done, "\n".join(txt.strip().splitlines()[1:])), flush=True)
            if n_done == "2":
                print("both lanes done", flush=True)
                break
            time.sleep(180)

    print("\n=== run analyzer ===")
    _remote.run(c, "cd /root/mk_v2 && %s -u _wc_analyze.py 2>&1" % PY, timeout=900)
    c.close()


if __name__ == "__main__":
    main()
