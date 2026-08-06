import _remote, sys
c = _remote.connect()
R = _remote.run
s = c.open_sftp(); s.put("_wc_analyze.py", "/root/mk_v2/_wc_analyze.py"); s.close()
R(c, "tail -6 /root/mk_v2_runs/e1/witness_confirmation/audit.log")
R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc_analyze.py", timeout=600)
c.close()
