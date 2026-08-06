import _remote
c = _remote.connect()
R = _remote.run
print("=== set pause marker ===")
R(c, "bash /root/mk_v2_runs/e3_b9_calib/pause_b9.sh", timeout=180)
print("=== chain trigger exit marker? ===")
R(c, "ls -la /root/mk_v2_runs/e3_b9_calib/CHAIN_TRIGGER_EXIT 2>&1; tail -3 /root/mk_v2_runs/e3_b9_calib/chain_trigger.log")
c.close()
print("DONE")
