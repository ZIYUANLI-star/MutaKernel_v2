"""Third sweep: what the two orchestrators will do next."""
import _remote

CMD = (
    "cat /root/mk_v2_runs/e3_b9_calib/chain_trigger.log; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/chain_trigger_stdout.log; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/keepalive_chain.log; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/keepalive_chain.sh; echo SEP; "
    "head -c 4000 /root/mk_v2/_b9_chain_trigger.py; echo SEP; "
    "head -c 6000 /root/mk_v2/_signoff_orch.py; echo SEP; "
    "for f in /root/mk_v2_runs/e3_b9_calib/lane*.log; do echo \"== $f\"; tail -c 400 $f; echo; done; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/completed_lane*.json; echo SEP; "
    "ps aux | grep -E 'b9|calib' | grep -v grep"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=120, echo=False)
c.close()
print(o)
print("MON3_DONE")
