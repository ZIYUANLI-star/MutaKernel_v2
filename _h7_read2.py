import _remote

c = _remote.connect()
for cmd in ["sed -n '255,277p' /root/mk_v2/_b9_resume_prep.py",
            "sed -n '140,338p' /root/mk_v2/_b9_calib_driver_v2.py"]:
    print("\n#### " + cmd)
    _remote.run(c, cmd, timeout=180)
c.close()
print("\nH7_DONE")
