"""Lane-M campaign watcher: 30-min probes, ALERT lines on anomalies.

Checks: runner/guard alive, observation count + rate, status mix, GPU,
disk, restart storm detection. Prints one summary line per cycle;
prefixes ALERT when something needs attention.
"""
import datetime
import json
import subprocess
import sys
import time

PROBE = r"""
import json, subprocess
OUT = '/root/mk_v2_runs/e3_campaign'
r = {}
def sh(cmd):
    return subprocess.run(['bash', '-c', cmd], capture_output=True,
                          text=True, timeout=60).stdout.strip()
r['runner'] = sh("pgrep -f 'run_fse_[e]xperiment.py.*e3-wave1-lane-m-v1' | head -1")
r['guard'] = sh("pgrep -f 'bash /root/mk_v2/guard_[l]ane_m.sh' | head -1")
r['obs'] = int(sh(f"wc -l < {OUT}/lane_m_run/observations.jsonl 2>/dev/null || echo 0"))
r['gpu'] = sh("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader")
r['disk'] = sh("df -h / | tail -1 | awk '{print $5}'")
r['restarts'] = sh(f"grep -c 'restart #' {OUT}/guard_lane_m.log 2>/dev/null || echo 0")
r['log_tail'] = sh(f"tail -1 {OUT}/lane_m_run.log 2>/dev/null")
import collections
try:
    st = collections.Counter()
    with open(f'{OUT}/lane_m_run/observations.jsonl') as fh:
        for line in fh:
            st[json.loads(line)['validation_status']] += 1
    r['statuses'] = dict(st)
except Exception as exc:
    r['statuses'] = {'probe_error': str(exc)[:60]}
print(json.dumps(r))
"""


def probe_once():
    code = (
        "import _remote as R, json, sys\n"
        "c = R.connect()\n"
        "sftp = c.open_sftp()\n"
        "with sftp.open('/root/mk_v2/_lane_m_probe.py', 'w') as fh:\n"
        "    fh.write(%r)\n"
        "sftp.close()\n"
        "code, o, e = R.run(c, 'cd /root/mk_v2 && "
        "/root/miniconda3/bin/python -u _lane_m_probe.py', "
        "timeout=120, echo=False)\n"
        "c.close()\n"
        "print(o.strip().splitlines()[-1])\n" % PROBE
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, timeout=300)
    lines = [l for l in out.stdout.strip().splitlines() if l.startswith("{")]
    if not lines:
        raise RuntimeError("probe failed: %s %s" % (out.stdout[-200:],
                                                    out.stderr[-200:]))
    return json.loads(lines[-1])


prev_obs, prev_t = None, None
fails = 0
while True:
    now = datetime.datetime.now().strftime("%H:%M")
    try:
        r = probe_once()
        fails = 0
        rate = ""
        if prev_obs is not None:
            dt_h = (time.time() - prev_t) / 3600.0
            rate = " rate=%.0f/h" % ((r["obs"] - prev_obs) / dt_h) if dt_h > 0 else ""
        prev_obs, prev_t = r["obs"], time.time()
        alert = ""
        if not r["runner"] and not r["guard"]:
            alert = "ALERT runner+guard both dead. "
        elif not r["guard"]:
            alert = "ALERT guard dead (runner still up). "
        elif not r["runner"] and r["obs"] < 107092:
            alert = "WARN runner down, guard should restart. "
        if int(r["restarts"]) > 20:
            alert += "ALERT restart storm (%s). " % r["restarts"]
        if r["obs"] >= 107092:
            print(f"[{now}] LANE M COMPLETE: {r['obs']} observations. statuses={r['statuses']}")
            break
        print(f"[{now}] {alert}obs={r['obs']}/107092{rate} statuses={r['statuses']} "
              f"gpu={r['gpu']} disk={r['disk']} restarts={r['restarts']}",
              flush=True)
    except Exception as exc:
        fails += 1
        print(f"[{now}] probe error ({fails}): {str(exc)[:120]}", flush=True)
        if fails >= 6:
            print(f"[{now}] ALERT 6 consecutive probe failures", flush=True)
            fails = 0
    time.sleep(1800)
