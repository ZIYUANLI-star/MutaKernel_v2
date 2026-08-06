import time
import _remote

DLOG = "/root/mk_v2_runs/final_window_trigger_drill.log"

c = _remote.connect()
done = False
for i in range(40):
    _, out, _ = _remote.run(c, f"grep -c 'orchestrator exit=' {DLOG}; true",
                            timeout=30, echo=False)
    n = out.strip().splitlines()[0] if out.strip() else "0"
    if n != "0":
        done = True
        break
    print(f"poll {i}: orchestrator not finished yet")
    time.sleep(20)
print("DONE_FLAG:", done)
print("--- drill trigger log (full, includes orchestrator dry-run output) ---")
_remote.run(c, f"cat {DLOG}", timeout=60)
c.close()
print("POLL_DONE")
