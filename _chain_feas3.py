"""Feasibility round 3: plan builder + runner validation requirements,
test_id derivation."""
import _remote as R

py = r"""
import subprocess

def sh(cmd):
    print(subprocess.run(['bash', '-c', cmd], capture_output=True,
                         text=True).stdout)

print('===== build_experiment_plan signature/body head =====')
sh("sed -n '440,560p' /root/mk_v2/src/experiments/protocol.py")

print('===== test_id derivation =====')
sh("grep -n -B3 -A10 'test_id' /root/mk_v2/src/experiments/protocol.py | head -60")

print('===== runner plan verification =====')
sh("grep -n -B2 -A6 'plan_sha256\|strategy_matrix_sha256\|verify\|_check' /root/mk_v2/scripts/run_fse_experiment.py | head -100")
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_feas3.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _feas3.py",
      timeout=300)
c.close()
print("FEAS3_DONE")
