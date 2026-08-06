"""B9 calibration FINAL aggregation (timestamp-correct dedup over all lanes).

Produces b9_calib_final_summary.json with:
  * true final status per unit (400 accounting, latest finished_at wins),
  * the three fragility ratios for blueprint 5.3 (unit-level, fp16-level,
    fp32-level) + borderline (single-grid-point) fp16 units,
  * distinct-error-value distributions fp16 vs fp32 (mechanism evidence),
  * control-sample false-positive rate,
  * unresolved units (never calibrated) listed explicitly.
"""
import _remote as R

agg_py = r"""
import glob, json
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path('/root/mk_v2_runs/e3_b9_calib')
q = json.load(open(OUT / 'queue_state.json'))
done = q['done'] if isinstance(q['done'], list) else list(q['done'])
universe = set(done) | set(q['pending']) | set(q['claimed'])
unit_dirs = {p.name for p in (OUT / 'units').iterdir() if p.is_dir()}
all_units = sorted(universe | unit_dirs)
print('universe from queue:', len(universe), '| unit dirs:', len(unit_dirs),
      '| union:', len(all_units))
assert len(all_units) == 400, len(all_units)

rows = {}
for f in sorted(glob.glob(str(OUT / 'calibration*.jsonl'))):
    for line in open(f):
        if line.strip():
            r = json.loads(line)
            u = r['unit']
            prev = rows.get(u)
            if prev is None or str(r.get('finished_at','')) >= str(prev.get('finished_at','')):
                rows[u] = r

missing = [u for u in all_units if u not in rows]
final = {u: rows[u] for u in all_units if u in rows}
stat = Counter(r['control_status'] for r in final.values())
print('units with rows:', len(final), 'missing rows:', missing)
print('TRUE final statuses:', dict(stat))

calibrated = {u: r for u, r in final.items()
              if r['control_status'] in ('calibrated_ok', 'calibrated_heavy_tail')}
ht = {u: r for u, r in calibrated.items()
      if r['control_status'] == 'calibrated_heavy_tail'}
fp16 = {u: r for u, r in calibrated.items() if r['dtype'] == 'float16'}
fp32 = {u: r for u, r in calibrated.items() if r['dtype'] == 'float32'}
ht16 = {u: r for u, r in ht.items() if r['dtype'] == 'float16'}
ht32 = {u: r for u, r in ht.items() if r['dtype'] == 'float32'}

# per-unit control error values (take trailing `cases` rows of the obs file)
def unit_errors(u, cases):
    d = OUT / 'units' / u
    obs = list(d.glob('b9_*_observations.jsonl'))
    if not obs:
        return None
    lines = [l for l in open(obs[0]) if l.strip()]
    vals = []
    for l in lines[-cases:]:
        r = json.loads(l)
        e = (r.get('b9') or {}).get('max_abs_err')
        if e is not None:
            vals.append(e)
    return vals

border16 = []          # fp16 calibrated_ok, all errors on ONE grid point
distinct16, distinct32 = [], []
fp_samples_bad, fp_samples_total = 0, 0
err_read_fail = []
for u, r in calibrated.items():
    vals = unit_errors(u, int(r.get('cases') or 32))
    if not vals:
        err_read_fail.append(u)
        continue
    nd = len(set(vals))
    tol = r.get('calibrated_tol')
    fp_samples_total += len(vals)
    if tol is not None:
        fp_samples_bad += sum(1 for v in vals if v > tol)
    if r['dtype'] == 'float16':
        distinct16.append(nd)
        if nd == 1 and r['control_status'] == 'calibrated_ok' and vals[0] > 0:
            border16.append(u)
    else:
        distinct32.append(nd)

unresolved = {u: final[u]['control_status'] for u in final
              if u not in calibrated}

def pct(a, b):
    return round(100.0 * a / b, 1) if b else None

summary = {
    'generated_at': __import__('datetime').datetime.now().isoformat(),
    'units_total': 400,
    'units_with_rows': len(final),
    'units_missing_rows': missing,
    'final_status_counts': dict(stat),
    'calibrated_total': len(calibrated),
    'fragility': {
        'heavy_tail_units': sorted(ht),
        'unit_level': [len(ht), len(calibrated), pct(len(ht), len(calibrated))],
        'fp16_level': [len(ht16), len(fp16), pct(len(ht16), len(fp16))],
        'fp32_level': [len(ht32), len(fp32), pct(len(ht32), len(fp32))],
        'borderline_fp16_single_grid_ok': sorted(border16),
        'borderline_fp16_count': len(border16),
        'control_sample_false_positive': [fp_samples_bad, fp_samples_total,
                                          pct(fp_samples_bad, fp_samples_total)],
    },
    'distinct_error_values': {
        'fp16_median': sorted(distinct16)[len(distinct16)//2] if distinct16 else None,
        'fp16_hist_1_2_3plus': [sum(1 for x in distinct16 if x == 1),
                                sum(1 for x in distinct16 if x == 2),
                                sum(1 for x in distinct16 if x >= 3)],
        'fp32_median': sorted(distinct32)[len(distinct32)//2] if distinct32 else None,
        'fp32_min': min(distinct32) if distinct32 else None,
    },
    'unresolved_units': unresolved,
    'error_read_failures': err_read_fail,
    'dedup_rule': 'latest finished_at wins across calibration*.jsonl (6 files)',
}
(OUT / 'b9_calib_final_summary.json').write_text(
    json.dumps(summary, indent=1), encoding='utf-8')
print(json.dumps(summary['fragility'], indent=1))
print('unresolved:', len(unresolved), dict(Counter(unresolved.values())))
print('distinct:', summary['distinct_error_values'])
print('B9_FINAL_AGG_DONE')
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_b9_final_agg.py", "w") as fh:
    fh.write(agg_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _b9_final_agg.py",
      timeout=900)
sftp = c.open_sftp()
sftp.get("/root/mk_v2_runs/e3_b9_calib/b9_calib_final_summary.json",
         "_b9_calib_final_summary.json")
sftp.close()
c.close()
print("AGG_FETCHED")
