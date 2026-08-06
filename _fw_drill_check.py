import _remote

c = _remote.connect()
for cmd in [
    "pgrep -af 'final_window_trigger' || echo NO_TRIGGER_PROC",
    "ls -la /root/mk_v2_runs/final_window_trigger_drill.log /root/mk_v2_runs/final_window_trigger_drill.lock 2>/dev/null",
    "cat /root/mk_v2_runs/final_window_trigger_drill.log 2>/dev/null",
    "ls /root/mk_v2_runs/e1/FW_DRILL_FAKE_MARK 2>/dev/null || echo NO_FAKE_MARK",
]:
    print("### " + cmd[:80])
    _remote.run(c, cmd, timeout=60)
c.close()
print("CHECK_DONE")
