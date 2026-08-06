"""Feasibility round 2: case-plan determinism, resume mechanics,
strategy schema (oracle knobs), site_directed API."""
import _remote as R

py = r"""
import json

print('===== strategy matrix: one full entry =====')
m = json.load(open('/root/mk_v2/configs/fse_strategy_matrix.json'))
strats = m if isinstance(m, list) else m.get('strategies', m)
if isinstance(strats, dict):
    strats = list(strats.values())
for s in strats:
    sid = s.get('id') or s.get('name')
    print(json.dumps(s)[:800])
    print('---')

print()
print('===== protocol.py: how test cases / test_id are derived =====')
import subprocess
out = subprocess.run(['grep', '-n', '-A', '3',
                      'test_id\|def build_experiment_plan\|def _case\|seed',
                      '/root/mk_v2/src/fse/protocol.py'],
                     capture_output=True, text=True)
print(out.stdout[:4000] if out.stdout else '(protocol.py not at src/fse)')
out = subprocess.run(['bash', '-c',
    "ls /root/mk_v2/src/*/protocol.py /root/mk_v2/src/protocol.py 2>/dev/null; "
    "grep -rn 'def build_experiment_plan' /root/mk_v2/src/ | head -5"],
    capture_output=True, text=True)
print(out.stdout)

print()
print('===== runner resume mechanics =====')
out = subprocess.run(['bash', '-c',
    "grep -n -B2 -A8 'completed\|resume\|already' "
    "/root/mk_v2/scripts/run_fse_experiment.py | head -80"],
    capture_output=True, text=True)
print(out.stdout)

print()
print('===== site_directed API =====')
out = subprocess.run(['bash', '-c',
    "grep -n 'def \|class ' /root/mk_v2/src/validator/site_directed.py"],
    capture_output=True, text=True)
print(out.stdout)

print()
print('===== oracle knobs: where tolerance comes from in worker =====')
out = subprocess.run(['bash', '-c',
    "grep -n 'atol\|rtol\|tolerance' /root/mk_v2/scripts/_candidate_worker.py | head -20"],
    capture_output=True, text=True)
print(out.stdout)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_feas2.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _feas2.py",
      timeout=600)
c.close()
print("FEAS2_DONE")
