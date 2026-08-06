import _remote

SCRIPT = r"""
import json, glob, statistics, datetime, collections

FIX_TS = datetime.datetime.fromisoformat('2026-07-29T02:27:33+00:00')  # 10:27:33 CST

def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else None

lanes = {}
for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane[0-5].jsonl')):
    lane = f.split('lane')[-1].split('.')[0]
    lanes[lane] = [json.loads(ln) for ln in open(f) if ln.strip()]

print('== OUTCOME DIST ==')
tot = collections.Counter()
for lane, recs in lanes.items():
    c = collections.Counter(r['outcome'] for r in recs)
    tot.update(c)
    print(f'lane{lane}: n={len(recs)}', dict(c))
print('TOTAL:', sum(tot.values()), dict(tot))

print()
print('== ALL FALSIFIED ==')
for lane, recs in lanes.items():
    for r in recs:
        if r['outcome'] == 'FALSIFIED':
            d = r.get('divergence') or {}
            print(json.dumps({'lane': lane, 'probe_id': r['probe_id'], 'fault_class': r.get('fault_class'),
                'policy': d.get('policy'), 'rt': d.get('round_type'), 'sub': d.get('sub_index'),
                'seed': d.get('seed'), 'detail': d.get('detail'), 'trials': len(r.get('trials') or []),
                'wall_s': round((r.get('wall_ms') or 0)/1000, 1), 'has_witness': bool(d),
                'pipeline': r.get('input_pipeline'), 'fin': r.get('finished_at')}))

print()
print('== ALL INCONCLUSIVE ==')
for lane, recs in lanes.items():
    for r in recs:
        if r['outcome'] == 'INCONCLUSIVE':
            print(json.dumps({'lane': lane, 'probe_id': r['probe_id'], 'class': r.get('inconclusive_class'),
                'valid': r.get('valid_rounds'), 'wall_s': round((r.get('wall_ms') or 0)/1000, 1),
                'fin': r.get('finished_at')}))

print()
print('== V2 (mem_fix) RECORDS ==')
v2walls = {'3': [], '5': []}
for lane in ('3', '5'):
    for r in lanes.get(lane, []):
        if r.get('input_pipeline') == 'cse_gen_opt_v2':
            trials = r.get('trials') or []
            rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
            sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
            np_ = sum(1 for t in trials if t.get('status') != 'pass')
            w = (r.get('wall_ms') or 0)/1000
            v2walls[lane].append(w)
            print(json.dumps({'lane': lane, 'probe_id': r['probe_id'], 'outcome': r['outcome'],
                'rand': rp, 'stress': sp, 'nonpass': np_, 'valid': r.get('valid_rounds'),
                'to': r.get('timed_out'), 'wall_s': round(w, 1), 'fin': r.get('finished_at')}))
print()
for lane in ('3', '5'):
    ws = v2walls[lane]
    if ws:
        print(f'lane{lane} v2 walls: n={len(ws)} median={statistics.median(ws):.0f}s p95={pct(ws,0.95):.0f}s max={max(ws):.0f}s')

# marker consistency: records finished after FIX_TS+30min should be v2
print()
print('== marker/time check (post 10:57 CST should be v2) ==')
bad = []
for lane in ('3', '5'):
    for r in lanes.get(lane, []):
        fin = datetime.datetime.fromisoformat(r['finished_at'])
        if fin >= FIX_TS and r.get('input_pipeline') != 'cse_gen_opt_v2':
            bad.append((lane, r['probe_id'], r.get('input_pipeline'), r['finished_at']))
print('records after fix without v2 tag:', bad)

print()
print('== GRADING CONSISTENCY ==')
bad_still, bad_fals = [], []
for lane, recs in lanes.items():
    for r in recs:
        trials = r.get('trials') or []
        rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
        sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
        if r['outcome'] == 'STILL_LIKELY_EQUIVALENT' and (rp < 40 or sp < 42):
            bad_still.append((lane, r['probe_id'], rp, sp))
        if r['outcome'] == 'FALSIFIED' and not r.get('divergence'):
            bad_fals.append((lane, r['probe_id']))
print('STILL below 40+42:', bad_still)
print('FALSIFIED missing witness:', bad_fals)

print()
print('== LEDGER/UNIQUE/HEARTBEAT ==')
seen = collections.defaultdict(list)
for lane, recs in lanes.items():
    comp = json.load(open(f'/root/mk_v2_runs/e1/cse_completed_lane{lane}.json'))
    comp_ids = set(comp if isinstance(comp, list) else comp.keys())
    obs_ids = set(r['probe_id'] for r in recs)
    if obs_ids != comp_ids or len(obs_ids) != len(recs):
        print(f'lane{lane} MISMATCH: obs={len(recs)} uniq_obs={len(obs_ids)} ledger={len(comp_ids)}')
    else:
        print(f'lane{lane}: obs=ledger={len(recs)} OK')
    for r in recs:
        seen[r['probe_id']].append(lane)
print('unique:', len(seen), 'dups:', {k: v for k, v in seen.items() if len(v) > 1})
hts = [json.loads(ln)['ts'] for ln in open('/root/mk_v2_runs/sentinel_heartbeat.jsonl') if ln.strip()]
print('heartbeats:', len(hts), 'gaps>700s:', [round(b-a) for a, b in zip(hts, hts[1:]) if b-a > 700])

# host mem peak since fix
mx, mx_at = 0, None
for ln in open('/root/mk_v2_runs/sentinel_heartbeat.jsonl'):
    h = json.loads(ln)
    if h['at'] >= '2026-07-29T10:27':
        if h['mem_used_gb'] > mx:
            mx, mx_at = h['mem_used_gb'], h['at']
print('host mem peak since fix:', mx, 'GB at', mx_at)
print('V2CHECK_DONE')
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:2000])

for name, cmd in [
    ("oom_kill_counter", "cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null"),
    ("errors", "for f in 3 5; do echo '--- lane'$f; tail -c 200000 /root/mk_v2_runs/e1_cse_lane$f.log | grep -inE 'error|oom|killed|traceback' | tail -6; done"),
    ("restarts", "for f in 3 4 5; do echo -n \"lane$f AUTORESTART: \"; grep -c AUTORESTART /root/mk_v2_runs/e1_cse_lane$f.log; done"),
    ("lane3_tail", "tail -8 /root/mk_v2_runs/e1_cse_lane3.log"),
    ("lane5_tail", "tail -8 /root/mk_v2_runs/e1_cse_lane5.log"),
]:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o.rstrip()[:2500])
c.close()
