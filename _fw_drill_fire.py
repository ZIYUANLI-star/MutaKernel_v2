import time
import _remote

DLOG = "/root/mk_v2_runs/final_window_trigger_drill.log"

c = _remote.connect()
_remote.run(c, "kill 231930 2>/dev/null; touch /root/mk_v2_runs/e1/FW_DRILL_FAKE_MARK && echo FAKE_MARK_SET", timeout=30)
for i in range(30):
    time.sleep(20)
    _, out, _ = _remote.run(c, f"grep -c 'FINAL_WINDOW_TRIGGERED_OK\\|orchestrator exit' {DLOG} 2>/dev/null || echo 0",
                            timeout=30, echo=False)
    if out.strip() and out.strip() != "0":
        break
    print(f"poll {i}: not done yet")
print("--- drill trigger log ---")
_remote.run(c, f"cat {DLOG}", timeout=60)
c.close()
print("FIRE_DONE")
