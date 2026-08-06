"""Poll sentinel health: process alive, heartbeat lines, log tail."""
import _remote

c = _remote.connect()
_remote.run(c, "PID=$(cat /root/mk_v2_runs/e1_sentinel.pid 2>/dev/null); "
               "echo sentinel_pid=$PID; ls /proc/$PID/cmdline >/dev/null 2>&1 "
               "&& echo SENTINEL_ALIVE || echo SENTINEL_DEAD; "
               "echo hb_lines=$(wc -l < /root/mk_v2_runs/sentinel_heartbeat.jsonl); "
               "tail -n 2 /root/mk_v2_runs/sentinel_heartbeat.jsonl; "
               "echo ---log---; tail -n 4 /root/mk_v2_runs/e1_sentinel.log; "
               "echo ---anomaly---; ls /root/mk_v2_runs/ANOMALY_* 2>/dev/null "
               "|| echo NO_ANOMALY_FILES",
            timeout=60)
c.close()
print("POLL_DONE")
