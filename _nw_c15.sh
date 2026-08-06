cd /root/mk_v2
/root/miniconda3/bin/python - <<'PY'
import glob, json
files = sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations*.jsonl'))
print('== every P37 CSE record ever written (incl. backups/archives) ==')
seen=set()
for p in files:
    for line in open(p, encoding='utf-8'):
        if not line.strip(): continue
        r=json.loads(line)
        pid=r.get('probe_id','')
        if not pid.startswith('L1_P37'): continue
        key=(p,pid,r.get('finished_at'))
        if key in seen: continue
        seen.add(key)
        d=r.get('divergence') or {}
        print('%-46s %-30s %-24s vr=%-4s policy=%-22s si=%-3s seed=%-6s %s' % (
            p.split('/')[-1][:46], pid, r.get('outcome'), r.get('valid_rounds'),
            d.get('policy'), d.get('sub_index'), d.get('seed'),
            r.get('finished_at')))
print()
print('== sparse_extreme round outcomes per P37 record in the sign-off requeue ==')
for line in open('/root/mk_v2_runs/e1/cse_observations_lane3_signoff_requeue.jsonl', encoding='utf-8'):
    r=json.loads(line)
    if not r['probe_id'].startswith('L1_P37'): continue
    rows=[(t.get('sub_index'), t.get('status')) for t in (r.get('trials') or [])
          if t.get('policy')=='sparse_extreme']
    print('%-34s %s' % (r['probe_id'], rows))
print()
print('== how many stress rounds diverged anywhere for these five ==')
for line in open('/root/mk_v2_runs/e1/cse_observations_lane3_signoff_requeue.jsonl', encoding='utf-8'):
    r=json.loads(line)
    if not r['probe_id'].startswith('L1_P37'): continue
    bad=[(t.get('policy'), t.get('sub_index'), t.get('status'))
         for t in (r.get('trials') or []) if t.get('status')!='pass']
    print('%-34s non-pass rounds: %s' % (r['probe_id'], bad))
PY
