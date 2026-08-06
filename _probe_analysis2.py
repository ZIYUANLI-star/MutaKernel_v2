import _remote

SCRIPT = r"""
import json, glob, statistics, datetime, collections

OPT_TS = datetime.datetime.fromisoformat('2026-07-28T04:56:37+00:00')  # 12:56:37 CST

def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]

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
print('== FALSIFIED LIST ==')
for lane, recs in lanes.items():
    for r in recs:
        if r['outcome'] in ('FALSIFIED', 'WITNESSED_NON_EQUIVALENT'):
            d = r.get('divergence') or {}
            print(json.dumps({'lane': lane, 'probe_id': r['probe_id'], 'fault_class': r.get('fault_class'),
                'policy': d.get('policy'), 'round_type': d.get('round_type'), 'sub_index': d.get('sub_index'),
                'seed': d.get('seed'), 'detail': d.get('detail'), 'trials': len(r.get('trials') or []),
                'wall_s': round((r.get('wall_ms') or 0)/1000, 1), 'has_witness': bool(d),
                'pipeline': r.get('input_pipeline'), 'finished_at': r.get('finished_at')}))

print()
print('== INCONCLUSIVE LIST ==')
for lane, recs in lanes.items():
    for r in recs:
        if r['outcome'] == 'INCONCLUSIVE':
            print(json.dumps({'lane': lane, 'probe_id': r['probe_id'], 'class': r.get('inconclusive_class'),
                'timed_out': r.get('timed_out'), 'valid_rounds': r.get('valid_rounds'),
                'wall_s': round((r.get('wall_ms') or 0)/1000, 1), 'finished_at': r.get('finished_at')}))

print()
print('== PRE/POST OPT SPLIT (marker + time) ==')
for lane in ('3', '4'):
    recs = lanes.get(lane, [])
    post = [r for r in recs if r.get('input_pipeline') == 'cse_gen_opt_v1']
    pre = [r for r in recs if r.get('input_pipeline') != 'cse_gen_opt_v1']
    for tag, grp in (('pre', pre), ('post', post)):
        walls = [(r.get('wall_ms') or 0)/1000 for r in grp]
        to = sum(1 for r in grp if r.get('timed_out'))
        if walls:
            print(f'lane{lane} {tag}-opt: n={len(walls)} median={statistics.median(walls):.0f}s '
                  f'p95={pct(walls,0.95):.0f}s max={max(walls):.0f}s timed_out={to}')
    # marker/time cross-check
    mism = [r['probe_id'] for r in recs
            if (datetime.datetime.fromisoformat(r['finished_at']) >= OPT_TS) != (r.get('input_pipeline') == 'cse_gen_opt_v1')]
    print(f'lane{lane} marker/time mismatches: {mism}')

print()
print('== POST-OPT RECORDS DETAIL ==')
for lane in ('3', '4', '5'):
    for r in lanes.get(lane, []):
        if r.get('input_pipeline') == 'cse_gen_opt_v1':
            trials = r.get('trials') or []
            rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
            sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
            np_ = [t for t in trials if t.get('status') != 'pass']
            print(json.dumps({'lane': lane, 'probe_id': r['probe_id'], 'outcome': r['outcome'],
                'rand_pass': rp, 'stress_pass': sp, 'nonpass': len(np_),
                'valid_rounds': r.get('valid_rounds'), 'timed_out': r.get('timed_out'),
                'wall_s': round((r.get('wall_ms') or 0)/1000, 1), 'finished_at': r.get('finished_at')}))

print()
print('== GRADING CONSISTENCY (all) ==')
bad_still, bad_fals = [], []
for lane, recs in lanes.items():
    for r in recs:
        trials = r.get('trials') or []
        rp = sum(1 for t in trials if t.get('round_type') == 'random' and t.get('status') == 'pass')
        sp = sum(1 for t in trials if t.get('round_type') == 'stress' and t.get('status') == 'pass')
        if r['outcome'] == 'STILL_LIKELY_EQUIVALENT' and (rp < 40 or sp < 42):
            ev = r.get('evidence') or {}
            bad_still.append((lane, r['probe_id'], rp, sp, bool(ev.get('resource_degraded'))))
        if r['outcome'] in ('FALSIFIED', 'WITNESSED_NON_EQUIVALENT') and not r.get('divergence'):
            bad_fals.append((lane, r['probe_id']))
print('STILL_LIKELY below strict 40+42:', bad_still)
print('FALSIFIED missing witness:', bad_fals)

print()
print('== THROUGHPUT post-opt ==')
now = datetime.datetime.now(datetime.timezone.utc)
for lane in ('3', '4'):
    post = [r for r in lanes.get(lane, []) if r.get('input_pipeline') == 'cse_gen_opt_v1']
    if post:
        ts = [datetime.datetime.fromisoformat(r['finished_at']) for r in post]
        span_h = (now - OPT_TS).total_seconds()/3600
        print(f'lane{lane}: post-opt done={len(post)} in {span_h:.2f}h -> {len(post)/span_h:.2f}/h; '
              f'last_finish={max(ts).isoformat()}')

print()
print('== LEDGER vs OBS + UNIQUENESS ==')
seen = collections.defaultdict(list)
for lane, recs in lanes.items():
    comp = json.load(open(f'/root/mk_v2_runs/e1/cse_completed_lane{lane}.json'))
    comp_ids = set(comp if isinstance(comp, list) else comp.keys())
    obs_ids = set(r['probe_id'] for r in recs)
    print(f'lane{lane}: obs={len(recs)} ledger={len(comp_ids)} obs-not-in-ledger={sorted(obs_ids-comp_ids)} ledger-not-in-obs={sorted(comp_ids-obs_ids)}')
    for r in recs:
        seen[r['probe_id']].append(lane)
dups = {k: v for k, v in seen.items() if len(v) > 1}
print('unique probes:', len(seen), 'cross-lane dups:', dups)

print()
print('== HEARTBEAT CONTINUITY ==')
hts = [json.loads(ln)['ts'] for ln in open('/root/mk_v2_runs/sentinel_heartbeat.jsonl') if ln.strip()]
gaps = [round(b - a) for a, b in zip(hts, hts[1:]) if b - a > 700]
print(f'entries={len(hts)} gaps>700s: {gaps}')
print('ANALYSIS_DONE')
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=300, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:2000])

for name, cmd in [
    ("lane3_tail", "tail -14 /root/mk_v2_runs/e1_cse_lane3.log"),
    ("lane4_tail", "tail -14 /root/mk_v2_runs/e1_cse_lane4.log"),
    ("lane5_tail", "tail -6 /root/mk_v2_runs/e1_cse_lane5.log"),
    ("errors", "for f in 3 4 5; do echo '--- lane'$f; tail -c 200000 /root/mk_v2_runs/e1_cse_lane$f.log | grep -inE 'error|oom|killed|traceback' | tail -8; done"),
    ("restarts", "for f in 3 4 5; do echo -n \"lane$f AUTORESTART: \"; grep -c AUTORESTART /root/mk_v2_runs/e1_cse_lane$f.log; done; grep -h 'AUTORESTART\\|LAUNCH' /root/mk_v2_runs/e1_cse_lane[345].log | tail -8"),
    ("manifest3", "tail -c 900 /root/mk_v2_runs/e1/cse_run_manifest_lane3.json"),
]:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o.rstrip())
c.close()
