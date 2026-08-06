import _remote as R

c = R.connect()
sftp = c.open_sftp()
sftp.put("_ops_src/wave2_prep.py", "/root/mk_v2_ops/wave2_prep.py")
sftp.close()
R.run(c, "cd /root/mk_v2_ops && /root/miniconda3/bin/python -u wave2_prep.py",
      timeout=1800)
c.close()
print("PREP_RUN_DONE")
