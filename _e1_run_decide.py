import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_e1_decide_remote.py", "/root/mk_v2/_e1_decide_remote.py")
sftp.close()
print("===== user diag (verify) =====")
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_diag23.py 2>&1 | tail -20", timeout=120)
print("===== decision dataset =====")
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_e1_decide_remote.py", timeout=120)
print("===== processes =====")
_remote.run(c, "date '+%F %T %z'; ps -eo pid,etime,args | awk '/run_e1_probe_study|e1_guard|_mutant_worker/ && !/awk/ {print $1, $2, $NF}'", timeout=30)
c.close()
print("RUN_DECIDE_DONE")
