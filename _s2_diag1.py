"""Diagnose why stage-2 guard has no driver running."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "print('top-level keys:', list(q.keys()))\n"
    "print('pending:', len(q.get('pending',[])))\n"
    "print('claimed:', len(q.get('claimed',{})))\n"
    "print('done:', len(q.get('done',{})) if isinstance(q.get('done'),dict) else len(q.get('done',[])))\n"
    "u=q['units']\n"
    "k0=list(u)[0]\n"
    "print('sample unit keys:', list(u[k0].keys())[:12])\n"
    "print('stage2_deferred:', len(q.get('stage2_deferred',[])))\n"
    "EOF\n"
    "echo ===GUARDLOGS===; ls -la /root/mk_v2_runs/e3_b9_calib/ | grep -i -E 'guard|s2|nohup' ; "
    "echo ===; tail -30 /root/mk_v2_runs/e3_b9_calib/guard_v2.log 2>/dev/null; "
    "tail -30 /root/mk_v2_runs/e3_b9_calib/s2_guard.log 2>/dev/null; "
    "echo ===PS===; ps -o pid,etime,cmd -p 463532; "
    "echo ===CHILDREN===; ps --ppid 463532 -o pid,etime,cmd 2>/dev/null; "
    "echo ===GUARD_SRC_HEAD===; head -40 /root/mk_v2/guard_b9_v2.sh 2>/dev/null || "
    "find /root -maxdepth 3 -name guard_b9_v2.sh 2>/dev/null"),
    timeout=60, echo=False)
print(o)
c.close()
