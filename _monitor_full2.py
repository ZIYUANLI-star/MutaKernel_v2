"""Second sweep: orchestrator/sentinel/queue details + e3_b9_calib activity."""
import _remote

CMD = (
    "cat /root/mk_v2_runs/signoff_orch.log; echo SEP; "
    "cat /root/mk_v2_runs/signoff_go.log; echo SEP; "
    "tail -c 3000 /root/mk_v2_runs/e1_sentinel.log; echo SEP; "
    "cat /root/mk_v2_runs/e1_sentinel_state.json; echo SEP; "
    "tail -c 2000 /root/mk_v2_runs/final_window_trigger.log; echo SEP; "
    "ls -la /root/mk_v2_runs/e3_b9_calib/ | tail -25; echo SEP; "
    "ls -la /root/mk_v2_runs/e3_b9_quantile_fix_check/; echo SEP; "
    "ps aux | grep -E 'sentinel|orch|e3|b9|guard' | grep -v grep; echo SEP; "
    "tail -c 1500 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log; echo SEP; "
    "ls /root/mk_v2_runs/e1/cse_lane_plan*.json /root/mk_v2_runs/e1/*signoff* 2>/dev/null; echo SEP; "
    "cat /root/mk_v2_runs/e1/CSE_DONE 2>/dev/null; echo; ls -la /root/mk_v2_runs/e1/CSE_DONE*"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=120, echo=False)
c.close()
print(o)
print("MON2_DONE")
