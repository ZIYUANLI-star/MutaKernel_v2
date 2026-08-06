import os
import _remote as R

c = R.connect()
sftp = c.open_sftp()
for remote, local in [
    ("/root/mk_v2/_e3_mk_input.py", "_remote_src/_e3_mk_input.py"),
    ("/root/mk_v2/_e3_plan_test_prep.py", "_remote_src/_e3_plan_test_prep.py"),
]:
    sftp.get(remote, local)
    print("fetched", local, os.path.getsize(local))
sftp.close()
c.close()
print("DONE")
