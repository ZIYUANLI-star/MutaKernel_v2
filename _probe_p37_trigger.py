import _remote

SCRIPT = r"""
import json
targets = {'L1_P37__arith_replace__14', 'L1_P37__sync_remove__1', 'L1_P37__sync_remove__0',
           'L1_P37__launch_config_mutate__0', 'L1_P37__epsilon_modify__0', 'L1_P39__relop_replace__6'}
for ln in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):
    r = json.loads(ln)
    if r['probe_id'] in targets:
        d = r['divergence']
        o = d.get('oracle') or {}
        mm = (o.get('mismatches') or [{}])[0]
        print(r['probe_id'])
        print('  policy/sub/seed:', d.get('policy'), d.get('sub_index'), d.get('seed'), '| detail:', d.get('detail'), '| errors:', d.get('errors'))
        print('  input:', json.dumps((d.get('input_summary') or [{}])[0])[:200])
        print('  mismatch:', str(mm.get('message'))[:150])
        print('  ref/cand:', str(mm.get('reference'))[:80], '||', str(mm.get('candidate'))[:80])
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[:1000])

for name, cmd in [
    ("trigger_proc", "ps -eo pid,ppid,etime,cmd | grep -E 'final_window' | grep -v grep"),
    ("trigger_files", "ls -la /root/mk_v2_runs/final_window.log /root/mk_v2_runs/*final* /root/mk_v2_runs/e1/*final* 2>/dev/null; ls /root/mk_v2 | grep -i final"),
    ("trigger_log", "tail -10 /root/mk_v2_runs/final_window.log 2>/dev/null; echo ---; tail -5 /root/mk_v2_runs/final_window_trigger.log 2>/dev/null"),
    ("done_lane3_absent", "ls /root/mk_v2_runs/e1/CSE_DONE_LANE3 2>&1"),
    ("p37_p39_remaining", "/root/miniconda3/bin/python -c \"import json; c=json.load(open('/root/mk_v2_runs/e1/cse_completed_lane3.json')); ids=c if isinstance(c,list) else list(c); print('done:',len(ids)); import collections; k=collections.Counter(i.split('__')[0] for i in ids); print(dict(k))\""),
]:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o.rstrip()[:2500])
    if e.strip():
        print("STDERR:", e[:400])
c.close()
