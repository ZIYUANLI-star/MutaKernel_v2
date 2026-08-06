"""Preflight: guard script, queue unit spec schema, task-module mapping."""
import _remote

CMD1 = "head -60 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.sh"
CMD2 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "print('keys:', list(qs.keys()))\n"
    "units = qs.get('units') or {}\n"
    "print('n unit specs:', len(units))\n"
    "k = 'L2_P14__float16'\n"
    "print(k, '->', json.dumps(units.get(k), ensure_ascii=False)[:500])\n"
    "print('pending sample:', qs.get('pending', [])[:3])\n"
    "print('wave:', qs.get('wave'))\n"
    "print('stage2_deferred n:', len(qs.get('stage2_deferred', [])))\n"
    "EOF\n"
)
CMD3 = (
    "grep -n 'task_module\\|candidate-module\\|task-module\\|plan.json' /root/mk_v2/_b9_calib_driver_v2.py | head -12; echo SEP; "
    "head -c 700 /root/mk_v2_runs/e3_b9_calib/units/L2_P14__float16/plan.json"
)

c = _remote.connect()
print('##### guard head #####')
_, o, _ = _remote.run(c, CMD1, timeout=60, echo=False)
print(o)
print('##### queue schema #####')
_, o, _ = _remote.run(c, CMD2, timeout=60, echo=False)
print(o)
print('##### driver module mapping #####')
_, o, _ = _remote.run(c, CMD3, timeout=60, echo=False)
c.close()
print(o)
print('PREFLIGHT_DONE')
