import _remote
c = _remote.connect()
R = _remote.run
s = c.open_sftp(); s.put("_wc_audit.py", "/root/mk_v2/_wc_audit.py"); s.close()
print("=== plan n_a=50 n_b=20 ===")
R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc_audit.py plan --n-a 50 --n-b 20", timeout=600)
print("=== b9 lane0 ===")
R(c, "tail -2 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; date")
c.close()
