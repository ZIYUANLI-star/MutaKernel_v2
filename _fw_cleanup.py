import _remote

c = _remote.connect()
_remote.run(c, "kill 232293 2>/dev/null; sleep 1; "
               "pgrep -af 'final_window_trigger.sh' ; true", timeout=30)
c.close()
print("CLEANUP_DONE")
