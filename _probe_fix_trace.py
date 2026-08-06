import _remote

SCRIPT = r"""
import json, datetime
# overnight host mem peak (from 7/28 23:00 CST to now)
mx, mx_at, over90 = 0, None, []
for ln in open('/root/mk_v2_runs/sentinel_heartbeat.jsonl'):
    h = json.loads(ln)
    if h['at'] >= '2026-07-28T23:00':
        if h['mem_used_gb'] > mx:
            mx, mx_at = h['mem_used_gb'], h['at']
        if h['mem_used_gb'] > 90:
            over90.append((h['at'], h['mem_used_gb']))
print('overnight host mem peak:', mx, 'at', mx_at, '| >90GB samples:', over90)

# new falsified witness detail
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane5.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] == 'L1_P41__init_modify__2':
        d = r['divergence']
        print('P41 witness:', json.dumps({k: d.get(k) for k in ('round_type','policy','sub_index','seed','detail')}))
        print('  oracle:', json.dumps(d.get('oracle', {}))[:400])
        print('  witness_fields:', r.get('witness_policy'), r.get('witness_round'), r.get('witness_seed'))
        break

# INC signature comparison P46 / P23
for f, pid in (('lane3','L1_P46__relop_replace__5'), ('lane5','L1_P23__mask_boundary__1')):
    for ln in open(f'/root/mk_v2_runs/e1/cse_observations_{f}.jsonl'):
        r = json.loads(ln)
        if r['probe_id'] == pid:
            st = {}
            for t in (r.get('trials') or []):
                st[t.get('status')] = st.get(t.get('status'), 0) + 1
            last = (r.get('trials') or [])[-1]
            print(pid, '| statuses:', st, '| last trial:', last.get('round_type'), last.get('policy'),
                  last.get('status'), '| pipeline:', r.get('input_pipeline'),
                  '| evidence:', json.dumps(r.get('evidence') or {})[:200])
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1000])

for name, cmd in [
    ("code_mtimes", "ls -la /root/mk_v2/scripts/_mutant_worker.py /root/mk_v2/scripts/run_e1_cse_falsify.py; ls -la /root/mk_v2/*.py 2>/dev/null | head -8"),
    ("fix_marker", "grep -n 'cse_gen_opt\\|cache' /root/mk_v2/scripts/_mutant_worker.py | head -12"),
    ("worker_rss_now", "ps -eo pid,rss,etime,cmd | grep _mutant_worker | grep -v grep"),
    ("sentinel_actions", "grep -c 'actions=0' /root/mk_v2_runs/e1_sentinel.log; grep -v 'actions=0' /root/mk_v2_runs/e1_sentinel.log | tail -5"),
]:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o.rstrip()[:3000])
    if e.strip():
        print("STDERR:", e[:400])
c.close()
