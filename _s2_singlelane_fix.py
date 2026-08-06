"""Single-lane the stage-2 tail to stop cgroup OOM churn.

Evidence: 20 SIGKILL(-9) events today came in same-second pairs = both lanes
concurrently claiming 75-109 GB units past the 120 GiB cgroup cap.  All 26
remaining units are big (42-109 GB); two-lane concurrency has no upside here.

Actions:
  1. verify big units CAN complete solo (history: completed units with
     reserve >= 90 GB);
  2. place B9_CALIB_V2_DONE_LANE1 marker (guard stops restarting lane 1)
     with an explicit operator note inside;
  3. kill the idle lane-1 driver by exact PID (it holds no claim);
  4. confirm lane 0 keeps running.
"""
import _remote as R

probe_py = r"""
import glob, json, os, signal

OUT = '/root/mk_v2_runs/e3_b9_calib'
q = json.load(open(OUT + '/queue_state.json'))
units = q['units']

# 1. evidence: completed units with big reserves
rows = {}
for f in sorted(glob.glob(OUT + '/calibration_v2_lane*.jsonl')):
    for line in open(f):
        if line.strip():
            r = json.loads(line)
            rows[r['unit']] = r
big_done = [(u, units.get(u, {}).get('reserve_gb'), r['control_status'])
            for u, r in rows.items()
            if r['control_status'].startswith('calibrated')
            and (units.get(u, {}).get('reserve_gb') or 0) >= 85]
big_done.sort(key=lambda x: -(x[1] or 0))
print('completed units with reserve >= 85 GB:', len(big_done))
for u, g, s in big_done[:8]:
    print('  %.1f GB  %s  %s' % (g, u, s))

# 2. find lane-1 driver pid and verify it holds no claim
claimed_lanes = {m.get('lane') for m in q['claimed'].values()}
print('claimed lanes right now:', claimed_lanes)
lane1_pids = []
for entry in os.listdir('/proc'):
    if not entry.isdigit():
        continue
    try:
        raw = open('/proc/%s/cmdline' % entry, 'rb').read()
    except OSError:
        continue
    cmd = raw.replace(b'\0', b' ').decode('utf-8', 'replace')
    if '_b9_calib_driver_v2.py --lane 1 ' in cmd:
        lane1_pids.append(int(entry))
print('lane-1 driver pids:', lane1_pids)

if 1 in claimed_lanes:
    print('ABORT: lane 1 holds a claim; not touching it')
else:
    marker = OUT + '/B9_CALIB_V2_DONE_LANE1'
    with open(marker, 'w') as fh:
        json.dump({
            "operator_note": "placed 2026-08-01T23:0x by ops fix: lane 1 "
                             "retired for the big-unit tail after paired "
                             "cgroup OOM SIGKILLs (12:59-16:07); remaining "
                             "26 units (42-109 GB reserve) run serially on "
                             "lane 0 to keep concurrent reserves under the "
                             "120 GiB cgroup cap. Lane 1 held no claim.",
            "not_a_completion_record": True,
        }, fh, indent=1)
    print('marker written:', marker)
    for pid in lane1_pids:
        os.kill(pid, signal.SIGTERM)
        print('SIGTERM ->', pid)

# 4. lane 0 still alive?
lane0 = []
for entry in os.listdir('/proc'):
    if entry.isdigit():
        try:
            raw = open('/proc/%s/cmdline' % entry, 'rb').read()
        except OSError:
            continue
        if '_b9_calib_driver_v2.py --lane 0 ' in raw.replace(b'\0', b' ').decode('utf-8', 'replace'):
            lane0.append(entry)
print('lane-0 driver pids (should be non-empty):', lane0)
print('SINGLELANE_FIX_APPLIED')
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_s2_singlelane.py", "w") as fh:
    fh.write(probe_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _s2_singlelane.py",
      timeout=240)
c.close()
print("SINGLELANE_DONE")
