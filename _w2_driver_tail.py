import _remote as R

c = R.connect()
R.run(c, "sed -n '240,340p' /root/mk_v2/_b9_calib_driver_v2.py", timeout=60)
R.run(c, "grep -n 'PAUSED\\|BRAKE\\|brake\\|marker' /root/mk_v2/_b9_calib_driver_v2.py | head -20",
      timeout=60)
c.close()
print("DONE")
