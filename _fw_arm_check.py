import _remote

c = _remote.connect()
for cmd in [
    "pgrep -af 'final_window_trigger.sh' ; true",
    "cat /root/mk_v2_runs/final_window_trigger.log 2>/dev/null",
    "ls -d /root/mk_v2_runs/final_window_trigger.lock 2>/dev/null || echo NO_LOCK",
    "ps -o pid,etime,args -p 200586 91971 108721 2>/dev/null",
]:
    print("### " + cmd[:80])
    _remote.run(c, cmd, timeout=30)
c.close()
print("ARM_CHECK_DONE")
