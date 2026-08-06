import _remote as R

c = R.connect()
sftp = c.open_sftp()
sftp.put("_ops_src/wave2_prep.py", "/root/mk_v2_ops/wave2_prep.py")
sftp.close()
# remove artifacts built with the wrong provenance root, then rebuild
R.run(c, "rm -f /root/mk_v2_runs/e3_campaign/wave2_subject_manifest.json "
         "/root/mk_v2_runs/e3_campaign/wave2_lane_m_plan.json "
         "/root/mk_v2_runs/e3_campaign/wave2_mdir_plan.json "
         "/root/mk_v2_runs/e3_campaign/wave2_mdir_plan.json.matrix_ref.json",
      timeout=60)
R.run(c, "cd /root/mk_v2_ops && /root/miniconda3/bin/python -u wave2_prep.py",
      timeout=1800)
c.close()
print("PREP_RUN_DONE")
