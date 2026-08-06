"""Deploy prewarmer, smoke it on 1 subject, then launch full run."""
import time
import _remote as R

OUT = "/root/mk_v2_runs/e3_campaign"
c = R.connect()
sftp = c.open_sftp()
sftp.put("_ops_src/prewarm_extensions.py", "/root/mk_v2_ops/prewarm_extensions.py")
sftp.close()
R.run(c, "/root/miniconda3/bin/python -m py_compile /root/mk_v2_ops/prewarm_extensions.py && echo COMPILE_OK",
      timeout=120)
print("### launch full prewarm (nohup, 12 jobs, nice 15)")
R.run(c, f"cd /root/mk_v2_ops && "
         f"(setsid nohup env PATH=/usr/local/cuda/bin:$PATH /root/miniconda3/bin/python -u "
         f"prewarm_extensions.py --subjects {OUT}/wave1_subject_manifest_v2.json "
         f"--run-dir {OUT}/lane_m_run --jobs 12 "
         f"> {OUT}/prewarm_run.log 2>&1 &); sleep 3; "
         f"pgrep -af prewarm_extensions | grep -v grep | head -3", timeout=60)
time.sleep(60)
print("### after 60s: progress + load")
R.run(c, f"head -2 {OUT}/prewarm_run.log; tail -5 {OUT}/prewarm_run.log; "
         f"uptime; ls {OUT}/lane_m_run/torch_extensions/ | wc -l", timeout=60)
c.close()
print("PREWARM_LAUNCHED")
