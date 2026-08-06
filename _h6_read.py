"""Read the rest of the queue builder + the lane driver."""
import _remote

c = _remote.connect()
for cmd in ["sed -n '80,260p' /root/mk_v2/_b9_resume_prep.py",
            "wc -l /root/mk_v2/_b9_resume_prep.py /root/mk_v2/_b9_calib_driver_v2.py",
            "sed -n '1,140p' /root/mk_v2/_b9_calib_driver_v2.py"]:
    print("\n#### " + cmd)
    _remote.run(c, cmd, timeout=180)
c.close()
print("\nH6_DONE")
