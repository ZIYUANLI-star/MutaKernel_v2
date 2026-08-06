import _remote, time
c = _remote.connect()
R = _remote.run
s = c.open_sftp()
s.put("_wc_audit.py", "/root/mk_v2/_wc_audit.py")
s.put("_wc_analyze.py", "/root/mk_v2/_wc_analyze.py")
s.put("_wc_p37_repro.py", "/root/mk_v2/_wc_p37_repro.py")
s.close()
print("=== plan n_A=10 ===")
R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc_audit.py plan --n-a 10 --n-b 20", timeout=300)
c.close()
