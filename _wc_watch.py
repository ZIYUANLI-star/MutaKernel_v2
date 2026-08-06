"""Local watcher for the witness-confirmation run (poll every 10 min).

Prints WC_STAGE_DONE_BOTH when both lanes have written STAGE_DONE, or
WC_ANOMALY when the run looks dead/stalled without finishing. Read-only.
"""
import time
import traceback

import _remote

POLL_S = 600
STALL_LIMIT = 3  # consecutive polls with no progress and no live worker

CMD = (
    "ls /root/mk_v2_runs/e1/witness_confirmation/STAGE_DONE_LANE0 2>/dev/null; "
    "ls /root/mk_v2_runs/e1/witness_confirmation/STAGE_DONE_LANE1 2>/dev/null; "
    "echo MARK; "
    "ps aux | grep -E '_wc_audit|witness_confirmation' | grep -v grep | wc -l; "
    "nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l; "
    "echo MARK; "
    "tail -n 2 /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log 2>/dev/null; "
    "tail -n 2 /root/mk_v2_runs/e1/witness_confirmation/audit_lane1.log 2>/dev/null; "
    "echo MARK; "
    "grep -ch . /root/mk_v2_runs/e1/witness_confirmation/*results*.jsonl "
    "/root/mk_v2_runs/e1/witness_confirmation/*observations*.jsonl 2>/dev/null | paste -sd+ | bc"
)


def poll():
    c = _remote.connect()
    try:
        _, out, _ = _remote.run(c, CMD, timeout=90, echo=False)
    finally:
        c.close()
    parts = out.split("MARK")
    done0 = "STAGE_DONE_LANE0" in parts[0]
    done1 = "STAGE_DONE_LANE1" in parts[0]
    nums = [x.strip() for x in parts[1].strip().splitlines() if x.strip()]
    n_procs = int(nums[0]) if nums else 0
    n_gpu = int(nums[1]) if len(nums) > 1 else 0
    tail = parts[2].strip().replace("\n", " | ")[:400]
    try:
        n_results = int(parts[3].strip() or 0)
    except Exception:
        n_results = -1
    return done0, done1, n_procs, n_gpu, tail, n_results


def main():
    stall = 0
    last_results = -1
    last_tail = ""
    while True:
        try:
            done0, done1, n_procs, n_gpu, tail, n_results = poll()
        except Exception as exc:
            print(f"[wc-watch {time.strftime('%F %T')}] poll error: {exc}", flush=True)
            traceback.print_exc()
            time.sleep(POLL_S)
            continue

        stamp = time.strftime("%F %T")
        print(f"[wc-watch {stamp}] done=({done0},{done1}) procs={n_procs} "
              f"gpu_apps={n_gpu} results={n_results} tail: {tail[:200]}", flush=True)

        if done0 and done1:
            print("WC_STAGE_DONE_BOTH -- witness confirmation finished; "
                  "ready for final recalc and blueprint fill", flush=True)
            break

        progressed = (n_results != last_results) or (tail != last_tail)
        last_results, last_tail = n_results, tail
        alive = n_procs > 0 or n_gpu > 0
        if not alive and not progressed:
            stall += 1
        else:
            stall = 0
        if stall >= STALL_LIMIT:
            print("WC_ANOMALY -- no audit process, no GPU app, no progress for "
                  f"{STALL_LIMIT} polls and STAGE_DONE missing; needs a look", flush=True)
            break

        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
