import _remote

c = _remote.connect()
_remote.run(c, "ls /root/mk_v2_runs/e1/EQUIV_DONE 2>/dev/null && echo MARKER_PRESENT || echo NOT_DONE; "
               "wc -l /root/mk_v2_runs/e1/equiv_observations_lane4_requeue.jsonl 2>/dev/null; "
               "tail -n 1 /root/mk_v2_runs/e1_equiv_lane4_requeue.log", timeout=30)
c.close()
