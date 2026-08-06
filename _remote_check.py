"""Deep health check of the run4 E0 driver."""
from _remote import connect, run

c = connect()
for cmd in [
    "tail -6 /root/mk_v2_runs/e0_run4_s0.log",
    "wc -l /root/mk_v2_runs/e0_run4_s0/observations.jsonl",
    "python3 2>/dev/null || true",
    "ls /root/mk_v2_runs/e0_run4_s0/worker_logs 2>/dev/null | wc -l",
    "cat /root/mk_v2_runs/e0_run4_s0/original_controls.json 2>/dev/null | /root/miniconda3/bin/python -c \"import json,sys; d=json.load(sys.stdin); print('controls done:', len(d)); import collections; c=collections.Counter((v['legacy']['status'], v['corrected']['status']) for v in d.values()); [print(k, v) for k, v in c.items()]\"",
    "ps -eo pid,etime,time,%cpu,cmd | grep -E '_mutant_[w]orker|run_e0_[f]lip' ",
    "date -u; stat -c '%y %n' /root/mk_v2_runs/e0_run4_s0/observations.jsonl",
    "tail -1 /root/mk_v2_runs/e0_run4_s0/observations.jsonl | /root/miniconda3/bin/python -c \"import json,sys; r=json.loads(sys.stdin.read()); print(r['probe_id'], r['historical_status'], 'leg:', r['legacy']['status'], 'cor:', r['corrected']['status'], 'ctrl', r['original_control_ok'], r['finished_at'])\"",
]:
    print("### " + cmd[:80])
    run(c, cmd, timeout=90)
c.close()
print("CHECK_DONE")
