"""Fix 2: move upload staging out of the repo, restore clean tree."""
import _remote as R

c = R.connect()
R.run(c, "mkdir -p /root/wave2_upload_archive && "
         "mv /root/mk_v2/external/C5_kernelbench_samples_wave2 "
         "/root/mk_v2/external/c5_wave2.tar.gz /root/wave2_upload_archive/ && "
         "echo MOVED", timeout=120)
print("### git status after move")
R.run(c, "cd /root/mk_v2 && git status --porcelain; echo status_exit=$?; "
         "git rev-parse HEAD", timeout=60)
R.run(c, "ls /root/wave2_upload_archive/", timeout=60)
c.close()
print("FIX2_DONE")
