import _remote
c = _remote.connect()
R = _remote.run
s = c.open_sftp(); s.put("_wc_audit.py", "/root/mk_v2/_wc_audit.py"); s.close()
for n in (20, 30, 50):
    print("############ n_A=%d ############" % n)
    R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc_audit.py plan --n-a %d --n-b 20 2>&1 | head -7" % n, timeout=300)
print("############ detail for n_A=30 ############")
R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc_audit.py plan --n-a 30 --n-b 20", timeout=300)
c.close()
