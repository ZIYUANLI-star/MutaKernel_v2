import os
import _remote as R

os.makedirs("_remote_src", exist_ok=True)
c = R.connect()
sftp = c.open_sftp()
for remote, local in [
    ("/root/mk_v2/src/experiments/protocol.py", "_remote_src/protocol.py"),
    ("/root/mk_v2/scripts/_candidate_worker.py", "_remote_src/_candidate_worker.py"),
    ("/root/mk_v2/scripts/run_fse_experiment.py", "_remote_src/run_fse_experiment.py"),
    ("/root/mk_v2/src/validator/site_directed.py", "_remote_src/site_directed.py"),
    ("/root/mk_v2/scripts/build_mdir_strategy_row.py", "_remote_src/build_mdir_strategy_row.py"),
    ("/root/mk_v2/scripts/plan_fse_experiment.py", "_remote_src/plan_fse_experiment.py"),
    ("/root/mk_v2/scripts/run_e3_external.py", "_remote_src/run_e3_external.py"),
    ("/root/mk_v2/scripts/b11_compute_sanitizer.py", "_remote_src/b11_compute_sanitizer.py"),
]:
    sftp.get(remote, local)
    print("fetched", local, os.path.getsize(local))
sftp.close()
c.close()
print("FETCH_DONE")
