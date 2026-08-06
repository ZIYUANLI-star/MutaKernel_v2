"""Probe the witness_confirmation stage and the stage1 chain."""
import _remote

CMD = (
    "cat /root/mk_v2_runs/e3_b9_calib/stage1_chain.log 2>/dev/null; echo SEP; "
    "head -c 3500 /root/mk_v2/_b9_stage1_chain.py 2>/dev/null; echo SEP; "
    "ls -la /root/mk_v2_runs/e1/witness_confirmation/ 2>/dev/null; echo SEP; "
    "cat /root/mk_v2_runs/e1/witness_confirmation/plan.json 2>/dev/null | head -c 1500; echo SEP; "
    "ls /root/mk_v2_runs/e1/witness_confirmation/*.jsonl 2>/dev/null; "
    "wc -l /root/mk_v2_runs/e1/witness_confirmation/*.jsonl 2>/dev/null; echo SEP; "
    "tail -c 2500 /root/mk_v2_runs/e1/witness_confirmation/*.log 2>/dev/null; echo SEP; "
    "ls -la /root/mk_v2_runs/*.log | tail -8; echo SEP; "
    "tail -c 1200 /root/mk_v2_runs/e1_sentinel.log; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN 2>/dev/null; echo; "
    "cat /root/mk_v2_runs/e3_b9_calib/CHAIN_TRIGGER_EXIT 2>/dev/null; echo; "
    "cat /root/mk_v2_runs/e3_b9_calib/CHAIN_TRIGGER_FIRED 2>/dev/null"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=120, echo=False)
c.close()
print(o)
print("MON5_DONE")
