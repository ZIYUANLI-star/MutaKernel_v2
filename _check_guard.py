import _remote as R

c = R.connect()
R.run(c, "ls -la /proc/572431/cwd; cat $(readlink /proc/572431/cwd)/guard_lane_m.sh",
      timeout=60)
c.close()
print("DONE")
