import _remote
c = _remote.connect()
R = _remote.run
R(c, "bash /root/mk_v2_runs/e3_b9_calib/pause_b9.sh", timeout=180)
c.close()
