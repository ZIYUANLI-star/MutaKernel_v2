import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put('_e1_baseline_close_check_remote.py', '/root/mk_v2/_e1_baseline_close_check_remote.py')
sftp.close()
_remote.run(c, '/root/miniconda3/bin/python /root/mk_v2/_e1_baseline_close_check_remote.py', timeout=180)
c.close()
print('GO_DONE')
