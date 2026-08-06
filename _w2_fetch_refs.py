import os
import _remote as R

os.makedirs("_remote_src", exist_ok=True)
c = R.connect()
sftp = c.open_sftp()
for remote, local in [
    ("/root/mk_v2/_c3_stage.py", "_remote_src/_c3_stage.py"),
    ("/root/mk_v2/_e3_c3wrap.py", "_remote_src/_e3_c3wrap.py"),
    ("/root/mk_v2/_c5_stage.py", "_remote_src/_c5_stage.py"),
    ("/root/mk_v2/scripts/contract_prereview.py",
     "_remote_src/contract_prereview.py"),
    ("/root/mk_v2/scripts/plan_fse_experiment.py",
     "_remote_src/plan_fse_experiment.py"),
]:
    try:
        sftp.get(remote, local)
        print("fetched", local, os.path.getsize(local))
    except FileNotFoundError:
        print("MISSING", remote)
sftp.close()

R.run(c, "head -c 2000 /root/mk_v2_runs/e3_campaign/wave1_manifest_input.jsonl",
      timeout=60)
R.run(c, "ls /root/mk_v2_runs/e2_reconcile/ /root/mk_v2/docs 2>/dev/null | head -30; "
         "find /root/mk_v2* -name '*审核底稿*' 2>/dev/null | head", timeout=60)
c.close()
print("FETCH_DONE")
