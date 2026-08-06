"""Verify whether the chain trigger came up despite the hung launch channel."""
import _remote

c = _remote.connect()
for cmd in [
    "date -Iseconds",
    "cat /root/mk_v2_runs/e3_b9_calib/chain_trigger.log 2>&1",
    "cat /root/mk_v2_runs/e3_b9_calib/chain_trigger_stdout.log 2>&1 | tail -20",
    "cat /root/mk_v2_runs/e3_b9_calib/chain_trigger.lock 2>&1",
    "ls -la /root/mk_v2_runs/e3_b9_calib/CHAIN_TRIGGER_FIRED 2>&1",
    "/root/miniconda3/bin/python -c \"import sys; sys.path.insert(0,'/root/mk_v2');"
    "import _b9_chain_trigger as t;"
    "print('trigger procs:', t.find_processes('_b9_chain_trigger.py'));"
    "print('b9 procs:', t.b9_processes())\"",
]:
    print("\n#### " + cmd[:80])
    _remote.run(c, cmd, timeout=180)
c.close()
print("\nH10_DONE")
