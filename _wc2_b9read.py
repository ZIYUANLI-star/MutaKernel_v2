import _remote
c = _remote.connect()
R = _remote.run
for f in ["pause_b9.sh", "guard_b9_v2.sh", "resume_b9.sh", "keepalive_chain.sh"]:
    print("===== " + f + " =====")
    R(c, "cat /root/mk_v2_runs/e3_b9_calib/" + f)
print("===== lane_v2 logs =====")
R(c, "tail -20 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo ---; tail -20 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log; echo ---; tail -20 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log")
print("===== completed_v2 =====")
R(c, "cat /root/mk_v2_runs/e3_b9_calib/completed_v2_lane0.json; echo; wc -l /root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl")
print("===== chain trigger tail =====")
R(c, "tail -25 /root/mk_v2_runs/e3_b9_calib/chain_trigger.log; echo ---; tail -15 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log")
c.close()
print("DONE")
