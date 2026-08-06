"""Upload and execute the requeue script; also probe cron availability."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_e1_requeue_remote.py", "/root/mk_v2/_e1_requeue_remote.py")
sftp.close()
print("===== requeue =====")
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_e1_requeue_remote.py", timeout=120)
print("===== verify counts =====")
_remote.run(
    c,
    "wc -l /root/mk_v2_runs/e1/equiv_observations.jsonl "
    "/root/mk_v2_runs/e1/equiv_observations_timeout_v1.jsonl "
    "/root/mk_v2_runs/e1/equiv_observations.jsonl.bak_timeoutfix; "
    "/root/miniconda3/bin/python -c \"import json; "
    "print('completed', len(json.load(open('/root/mk_v2_runs/e1/equiv_completed.json')))); "
    "print('completed_bak', len(json.load(open('/root/mk_v2_runs/e1/equiv_completed.json.bak_timeoutfix'))))\"",
    timeout=60,
)
print("===== cron availability =====")
_remote.run(c, "pgrep -x cron || pgrep -x crond || echo NO_CRON_DAEMON; which cron crontab 2>/dev/null", timeout=30)
c.close()
print("REQUEUE_DRIVER_DONE")
