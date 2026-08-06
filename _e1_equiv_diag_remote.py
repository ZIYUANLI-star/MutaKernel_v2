import json, collections
recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/equiv_observations.jsonl') if l.strip()]
print('total', len(recs))
print(collections.Counter(r.get('grade') or r.get('status') for r in recs))
inc = [r for r in recs if (r.get('grade') or r.get('status')) == 'INCONCLUSIVE']
reasons = collections.Counter()
for r in inc:
    reason = (r.get('reason') or r.get('inconclusive_class') or
              str(r.get('error') or '')[:80] or 'unspecified')
    reasons[reason] += 1
for k, v in reasons.most_common(10):
    print(f'  {v}x  {k}')
print('--- first 3 INCONCLUSIVE records (trimmed) ---')
for r in inc[:3]:
    slim = {k: (str(v)[:200] if not isinstance(v, (int, float)) else v)
            for k, v in r.items() if k not in ('evidence', 'trials')}
    print(json.dumps(slim, ensure_ascii=False)[:600])
print('--- ordering: index of first INCONCLUSIVE run ---')
for i, r in enumerate(recs):
    if (r.get('grade') or r.get('status')) == 'INCONCLUSIVE':
        print('first INCONCLUSIVE at index', i, 'probe', r.get('probe_id'))
        break
print('--- last 5 records probe_ids + grades ---')
for r in recs[-5:]:
    print(' ', r.get('probe_id'), (r.get('grade') or r.get('status')))
import subprocess
print('--- dmesg OOM check ---')
try:
    out = subprocess.run("dmesg -T 2>/dev/null | grep -iE 'killed process|out of memory' | tail -5",
                         shell=True, capture_output=True, text=True, timeout=30)
    print(out.stdout or '(no OOM lines)')
except Exception as exc:
    print('dmesg failed:', exc)
print('DIAG_DONE')
