import _remote

SCRIPT = r"""
import json, glob, statistics, datetime

# 1) matched-kernel pre/post walls, lane4 L1_P20 and lane3 L1_P35
for lane, kern in (('4', 'L1_P20'), ('3', 'L1_P35')):
    pre, post = [], []
    for ln in open(f'/root/mk_v2_runs/e1/cse_observations_lane{lane}.jsonl'):
        r = json.loads(ln)
        if r.get('kernel') == kern and r['outcome'] == 'STILL_LIKELY_EQUIVALENT':
            w = round((r.get('wall_ms') or 0)/1000)
            (post if r.get('input_pipeline') == 'cse_gen_opt_v1' else pre).append((r['probe_id'], w, r.get('timed_out')))
    print(f'{kern} lane{lane} pre-opt STILL walls:', pre)
    print(f'{kern} lane{lane} post-opt STILL walls:', post)

# 2) nonpass rounds of L1_P35__relop_replace__7
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] == 'L1_P35__relop_replace__7':
        for t in (r.get('trials') or []):
            if t.get('status') != 'pass':
                print('nonpass:', t.get('round_type'), t.get('policy'), t.get('status'),
                      str(t.get('reason'))[:150], 'round_timeout=', t.get('round_timeout'))
        print('evidence:', json.dumps(r.get('evidence') or {})[:400])

# 3) heartbeat mem peak since opt deploy
OPT = 1785214597  # 2026-07-28 12:56:37 CST
mems, gmems = [], []
for ln in open('/root/mk_v2_runs/sentinel_heartbeat.jsonl'):
    h = json.loads(ln)
    if h['ts'] >= OPT:
        mems.append(h['mem_used_gb'])
        gmems.append(h['gpu_mem_used_mib'][0])
print('post-opt heartbeats:', len(mems), 'host mem min/max:', min(mems), max(mems),
      'gpu mem min/max:', min(gmems), max(gmems))
print('FINAL2_DONE')
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1500])
print("== GPU util samples ==")
code, o, e = _remote.run(c, "for i in 1 2 3 4 5 6; do nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; sleep 2; done", timeout=60, echo=False)
print(o)
c.close()
