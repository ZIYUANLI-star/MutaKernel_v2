"""Stage-level picture of the WC-1 audit: driver liveness, per-lane stage
progression, cell inventory, and whether the analyzer's inputs are all present.
"""
import time

import _remote

WC = "/root/mk_v2_runs/e1/witness_confirmation"
E1 = "/root/mk_v2_runs/e1"

CMDS = [
    ("driver", "ps -o pid,ppid,etime,cmd -p 290038 2>/dev/null || echo 'driver 290038 GONE'"),
    ("wc procs", "ps -eo pid,ppid,etime,cmd | grep -E '[_]wc_(start|audit)' | grep -v grep || echo none"),
    ("workers", "ps -eo pid,etime,cmd | grep '[m]utant_worker' | cut -c1-150 || echo none"),
    ("stage files", "ls -la %s/ | grep -Ei 'stage|done|lock' || echo 'no stage/done markers'" % WC),
    ("cells", "ls %s/cells/ 2>/dev/null | wc -l" % WC),
    ("cell names", "ls %s/cells/ 2>/dev/null | head -60" % WC),
    ("lane0 tail", "tail -6 %s/audit_lane0.log" % WC),
    ("lane1 tail", "tail -6 %s/audit_lane1.log" % WC),
    ("start log", "ls %s/*.log; tail -25 %s/wc_start.log 2>/dev/null || echo 'no wc_start.log'" % (WC, WC)),
    ("analyzer inputs",
     "for f in %s/_wc_witness_inventory.json %s/_wc_round_counts.json %s/plan.json; do "
     "if [ -f $f ]; then echo \"OK   $(stat -c '%%s bytes' $f)  $f\"; else echo \"MISS $f\"; fi; done"
     % (E1, E1, WC)),
    ("analyzer deployed", "ls -la /root/_wc_analyze.py /root/mk_v2/scripts/_wc_analyze.py 2>&1 | cut -c1-140"),
    ("plan shape",
     "python3 -c \"import json;p=json.load(open('%s/plan.json'));"
     "print('control_cells',len(p['control_cells']),'confirm_cells',len(p['confirm_cells']));"
     "print('lanes', sorted(set(c.get('lane') for c in p['control_cells']+p['confirm_cells'])))\"" % WC),
    ("gpu", "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"),
    ("oom", "cat /sys/fs/cgroup/memory/memory.failcnt 2>/dev/null; "
            "grep -c 'oom_kill' /dev/kmsg 2>/dev/null; "
            "dmesg 2>/dev/null | grep -ci 'killed process' || echo 'dmesg unavailable'"),
]


def main():
    last = None
    for attempt in range(5):
        try:
            c = _remote.connect()
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            print("connect attempt %d failed: %s" % (attempt + 1, exc))
            time.sleep([20, 40, 60, 90][min(attempt, 3)])
    else:
        raise SystemExit("all connect attempts failed: %s" % last)

    for label, cmd in CMDS:
        print("\n=== %s ===" % label)
        try:
            _remote.run(c, cmd, timeout=90)
        except Exception as exc:  # noqa: BLE001
            print("  (command failed: %s)" % exc)
    c.close()


if __name__ == "__main__":
    main()
