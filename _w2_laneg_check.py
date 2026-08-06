import _remote as R

c = R.connect()
print("### wave15 s4_lane_g body")
R.run(c, "sed -n '/def s4_lane_g/,/def s5_lane_la/p' /root/mk_v2_ops/wave15_orchestrator.py",
      timeout=60)
c.close()
print("DONE")
