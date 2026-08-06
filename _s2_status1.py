"""Check B9 stage-2 progress + GPU + E3 readiness snapshot."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "date; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; echo ---; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "from collections import Counter\n"
    "st=Counter(u.get('status') for u in q['units'].values())\n"
    "print('unit status:', dict(st))\n"
    "done=[u for u in q['units'].values() if u.get('status')=='done']\n"
    "s2=[u for k,u in q['units'].items() if u.get('stage')==2 or u.get('stage2')]\n"
    "print('total units:', len(q['units']))\n"
    "EOF\n"
    "echo ---; tail -6 /root/mk_v2_runs/e3_b9_calib/guard.log 2>/dev/null; echo ---; "
    "ls /root/mk_v2_runs/e3_b9_calib/*.log 2>/dev/null | tail -5; echo ---; "
    "pgrep -af '[g]uard_b9_v2|[_]b9_calib_driver_v2' | head -5"),
    timeout=60, echo=False)
print(o)
c.close()
