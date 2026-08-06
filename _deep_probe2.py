"""Evening deep probe: stage-1 progress, wcfu chain, errors, system health."""
import _remote

CMD1 = (
    "date '+NOW=%F %T'; echo SEP; "
    "pgrep -af '_wcfu_chain|_b9_stage1_chain|e1_sentinel' | head; echo SEP; "
    "ps aux | grep -E 'run_e3_external|_b9_calib_driver|_wc_audit' | grep -v grep | awk '{print $2, $3\"%\", $6/1048576\"G\", substr($0, index($0,$11), 120)}'; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv,noheader; "
    "free -g | sed -n 2p; df -h /root | tail -1; uptime | awk -F'load average:' '{print $2}'; "
    "grep oom_kill /sys/fs/cgroup/memory/memory.oom_control"
)

CMD2 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "from collections import Counter\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "print('wave', qs['wave'], '| done', len(qs['done']), '| pending', len(qs['pending']), '| claimed', len(qs.get('claimed', {})))\n"
    "print(dict(Counter(qs['done'].values())))\n"
    "for u, m in qs.get('claimed', {}).items():\n"
    "    print('claimed:', u, m.get('since'), 'reserve', m.get('reserve_gb'))\n"
    "EOF\n"
    "echo SEP; "
    "tail -n 6 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo '---'; "
    "tail -n 6 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log; echo SEP; "
    "tail -n 3 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log; echo SEP; "
    "tail -n 3 /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log; echo SEP; "
    "grep -hE 'run_error|SIGKILL|Traceback' /root/mk_v2_runs/e3_b9_calib/lane_v2_*.log | tail -5; echo SEP; "
    "tail -c 300 /root/mk_v2_runs/e1_sentinel.log; echo SEP; "
    "ls /root/mk_v2_runs/e3_b9_calib/STAGE1_DONE /root/mk_v2_runs/e3_b9_calib/WCFU_DONE /root/mk_v2_runs/e3_b9_calib/WCFU_BLOCKED 2>/dev/null; echo ENDMARKERS"
)

c = _remote.connect()
print('##### SYSTEM #####')
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print('##### PROGRESS #####')
_, o, _ = _remote.run(c, CMD2, timeout=240, echo=False)
c.close()
print(o)
print('DEEP_PROBE2_DONE')
