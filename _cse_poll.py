import _remote

c = _remote.connect()
_remote.run(c, "date '+%F %T %z'; ls /root/mk_v2_runs/e1/CSE_DONE* 2>/dev/null || echo NO_MARKERS; "
               "for L in 0 1 2; do echo -n \"lane$L obs: \"; wc -l < /root/mk_v2_runs/e1/cse_observations_lane$L.jsonl 2>/dev/null || echo 0; done; "
               "ps -eo args | grep -cE 'run_e1_cse_falsify.py --out' ; "
               "grep -ciE 'traceback|out of memory|AUTORESTART' /root/mk_v2_runs/e1_cse_lane0.log /root/mk_v2_runs/e1_cse_lane1.log /root/mk_v2_runs/e1_cse_lane2.log",
            timeout=60)
c.close()
print("POLL_DONE")
