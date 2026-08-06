"""Health check: stage-2 drivers, GPU, queue, lane logs, memory, oom."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "date; echo ===PROC===; "
    "ps -o pid,etime,%cpu,rss,cmd -p $(pgrep -d, -f '[_]b9_calib_driver_v2') 2>/dev/null; "
    "echo ===GPU===; nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw --format=csv,noheader; "
    "echo ===QUEUE===; /root/miniconda3/bin/python -c \"import json; "
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
    "print('pending',len(q['pending']),'claimed',len(q['claimed']),'done',len(q['done'])); "
    "print(json.dumps(q['claimed'],indent=1))\"; "
    "echo ===LANE0===; tail -6 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; "
    "echo ===LANE1===; tail -6 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log; "
    "echo ===GUARD===; tail -3 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log; "
    "echo ===MEM===; free -g | head -2; "
    "echo ===OOM===; dmesg -T 2>/dev/null | grep -i 'oom\\|killed process' | tail -3; "
    "echo ===UNITDIR===; ls -lat /root/mk_v2_runs/e3_b9_calib/units/ 2>/dev/null | head -6"),
    timeout=90, echo=False)
print(o)
c.close()
