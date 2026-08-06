import _remote

SCRIPT = r"""
import json
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] == 'L1_P52__arith_replace__11':
        trials = r.pop('trials', [])
        print('RECORD (sans trials):')
        print(json.dumps(r, indent=1)[:3000])
        print('n_trials:', len(trials))
        st = {}
        for t in trials:
            st[t.get('status')] = st.get(t.get('status'), 0) + 1
        print('trial statuses:', st)
        print('last 2 trials:')
        for t in trials[-2:]:
            t2 = {k: v for k, v in t.items() if k != 'timings_ms'}
            print(json.dumps(t2)[:1200])
        break
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1500])

for name, cmd in [
    ("lane5_launch_log", "grep -A4 'LAUNCH cse lane 5' /root/mk_v2_runs/e1_cse_lane5.log | tail -12; grep 'targets' /root/mk_v2_runs/e1_cse_lane5.log | tail -3"),
    ("worker_dir_92kkbqde", "ls -la /root/mk_v2_runs/e1/e1cse_92kkbqde/"),
    ("worker_logs_search", "ls /root/mk_v2_runs/e1/e1cse_92kkbqde/../ 2>/dev/null | grep -i p52 ; find /root/mk_v2_runs/e1 -name '*P52*arith*11*' 2>/dev/null"),
    ("dmesg_around", "dmesg -T 2>/dev/null | tail -20"),
    ("lane4_summary", "cat /root/mk_v2_runs/e1/cse_summary_lane4.json"),
    ("lane5_manifest", "tail -c 500 /root/mk_v2_runs/e1/cse_run_manifest_lane5.json"),
]:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o.rstrip()[:3000])
    if e.strip():
        print("STDERR:", e[:500])
c.close()
