"""Mid-morning probe: confirm idle-but-healthy state, no stray processes."""
import _remote

CMD1 = (
    "date '+NOW=%F %T'; echo SEP; "
    "ps aux | grep -E 'run_e3_external|_b9_calib|_wc_audit|_wcfu|_mutant_worker|e1_sentinel|stage1_chain|guard' "
    "| grep -v grep | awk '{print $2, $3\"%\", int($6/1024)\"MB\", substr($0, index($0,$11), 110)}'; echo SEP; "
    "nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv,noheader; echo SEP; "
    "free -g | sed -n 2p; df -h /root | tail -1; uptime | awk -F'load average:' '{print $2}'; "
    "grep oom_kill /sys/fs/cgroup/memory/memory.oom_control"
)

CMD2 = (
    "ls /root/mk_v2_runs/e3_b9_calib/ | grep -E 'DONE|BLOCKED|FIRED' ; echo SEP; "
    "/root/miniconda3/bin/python /root/mk_v2/_b9_brake.py status | head -5; echo SEP; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "from collections import Counter\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "print('wave', qs['wave'], '| done', len(qs['done']), '| pending', len(qs['pending']), '| claimed', len(qs.get('claimed', {})))\n"
    "print('statuses:', dict(Counter(qs['done'].values())))\n"
    "print('stage2_deferred:', len(qs.get('stage2_deferred', [])))\n"
    "EOF\n"
    "echo SEP; "
    "tail -n 3 /root/mk_v2_runs/e1_sentinel.log; echo SEP; "
    "tail -n 2 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log; echo SEP; "
    "crontab -l 2>/dev/null | tail -5"
)

c = _remote.connect()
print('##### processes & system #####')
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print('##### markers & queue & duty #####')
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
c.close()
print(o)
print('IDLE_PROBE_DONE')
