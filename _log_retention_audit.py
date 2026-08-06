"""Audit log completeness & retention for the future blind audit."""
import _remote as R

py = r"""
import json, glob, os, subprocess

base = '/root/mk_v2_runs/e3_campaign'
run = base + '/lane_m_run'

obs = sum(1 for l in open(run + '/observations.jsonl') if l.strip())
wlogs = glob.glob(run + '/worker_logs/*.log')
print('observations:', obs)
print('worker_logs files:', len(wlogs))

# does one observation embed full trial detail?
r = json.loads(open(run + '/observations.jsonl').readline())
wr = r.get('worker_result') or {}
print('obs embeds worker_result keys:', sorted(wr.keys())[:12])

# sample worker log size
if wlogs:
    sz = sorted(os.path.getsize(f) for f in wlogs)
    print('worker log size bytes: min %d median %d max %d' %
          (sz[0], sz[len(sz)//2], sz[-1]))

# total sizes + disk
du = subprocess.run(['du', '-sh', run, base], capture_output=True,
                    text=True).stdout
print(du.strip())
df = subprocess.run(['df', '-h', '/root'], capture_output=True,
                    text=True).stdout.splitlines()[-1]
print('disk:', df)

# retention check: does the runner ever delete worker logs? worker_tmp count
print('worker_tmp files:', len(glob.glob(run + '/worker_tmp/*')))

# other campaign logs
for f in [base + '/lane_m_run.log', base + '/guard_lane_m.log']:
    print(f.split('/')[-1], os.path.getsize(f), 'bytes')
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_log_audit.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _log_audit.py",
      timeout=300)
print("### does runner code delete worker logs?")
R.run(c, "grep -n 'unlink\\|remove\\|rmtree\\|cleanup' /root/mk_v2/scripts/run_fse_experiment.py | head",
      timeout=60)
c.close()
print("LOG_AUDIT_DONE")
