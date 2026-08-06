import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "pgrep -af '[_]rq7_requeue.py'; echo ---; "
    "cat /root/mk_v2_runs/e1/requeue_final/run.log 2>/dev/null; echo ---; "
    "tail -10 /root/mk_v2_runs/e1/requeue_final/nohup.out 2>/dev/null; echo ---; "
    "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader"),
    timeout=60, echo=False)
print(o)
c.close()
print('RQ7_CHECK_DONE')
