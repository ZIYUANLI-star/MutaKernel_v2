import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "ls /root/mk_v2_runs/e1/requeue_final/RQ7_DONE 2>/dev/null && echo RQ7_MARK_OK; "
    "cat /root/mk_v2_runs/e1/requeue_final/run_summary.json 2>/dev/null | head -30; echo ---; "
    "tail -5 /root/mk_v2_runs/e3_b9_calib/s2_chain.log; echo ---; "
    "ls /root/mk_v2_runs/e3_b9_calib/S2_CHAIN_FIRED /root/mk_v2_runs/e3_b9_calib/S2_CHAIN_BLOCKED 2>/dev/null; echo ---; "
    "pgrep -af '[_]b9_calib_driver_v2|[g]uard_b9_v2|[_]s2_chain'; echo ---; "
    "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader"),
    timeout=60, echo=False)
print(o)
c.close()
print('DONE')
