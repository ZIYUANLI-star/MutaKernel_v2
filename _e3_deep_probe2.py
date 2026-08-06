"""Deep campaign probe: progress, mix, per-subject timing, guard, GPU."""
import _remote as R

py = r"""
import collections, json
OUT = '/root/mk_v2_runs/e3_campaign'
rows = [json.loads(l) for l in open(OUT + '/lane_m_run/observations.jsonl')]
print('obs:', len(rows))
print('statuses:', dict(collections.Counter(r['validation_status'] for r in rows)))
subj = collections.Counter(r['subject_id'] for r in rows)
print('subjects touched:', len(subj))
by_subj = collections.defaultdict(list)
for r in rows:
    by_subj[r['subject_id']].append(r)
for s, rs in sorted(by_subj.items()):
    st = collections.Counter(x['validation_status'] for x in rs)
    w = sum(x['parent_wall_ms'] for x in rs) / 1000
    print('  %-38s n=%-3d %s total_wall=%.0fs' % (s[:38], len(rs), dict(st), w))
# wall time distribution
w = sorted(r['parent_wall_ms'] / 1000 for r in rows)
if w:
    print('wall s: min %.1f p50 %.1f p90 %.1f max %.1f' % (
        w[0], w[len(w)//2], w[int(len(w)*0.9)], w[-1]))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_dp2.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_dp2.py",
      timeout=120)
print("### runner / guard / gpu")
R.run(c, "pgrep -f 'run_fse_experiment.py.*lane-m' | head -2; "
         "tail -2 /root/mk_v2_runs/e3_campaign/guard_lane_m.log; "
         "nvidia-smi --query-gpu=utilization.gpu,memory.used "
         "--format=csv,noheader; "
         "tail -2 /root/mk_v2_runs/e3_campaign/lane_m_run.log", timeout=60)
c.close()
print("DEEP2_DONE")
