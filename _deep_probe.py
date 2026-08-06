"""Deep probe of the running B9 stage-1 campaign + system health."""
import _remote

CMD1 = (
    "date '+NOW=%F %T'; echo SEP; "
    "ps aux | grep -E 'run_e3_external|_b9|_wc|_mutant|guard|sentinel' | grep -v grep; echo SEP; "
    "nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv,noheader; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo SEP; "
    "free -g | sed -n 2p; df -h /root | tail -1; uptime; echo SEP; "
    "grep -H oom_kill /sys/fs/cgroup/memory/memory.oom_control"
)

CMD2 = (
    "tail -n 10 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo SEP; "
    "tail -n 10 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log; echo SEP; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, time\n"
    "from collections import Counter\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "d = qs['done']\n"
    "print('wave', qs.get('wave'), '| done', len(d), '| pending', len(qs.get('pending', [])))\n"
    "print(dict(Counter(d.values())))\n"
    "print('claimed:')\n"
    "for u, meta in qs.get('claimed', {}).items():\n"
    "    print(' ', u, meta)\n"
    "EOF\n"
    "echo SEP; "
    "tail -n 4 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log; echo SEP; "
    "grep -hE 'run_error|driver_exception|Traceback|SIGKILL' /root/mk_v2_runs/e3_b9_calib/lane_v2_*.log | tail -8; echo SEP; "
    "tail -c 400 /root/mk_v2_runs/e1_sentinel.log"
)

# per-unit wall trend of last 20 completed units (from lane logs)
CMD3 = (
    "grep -hE 'calibrated_ok|controls_incomplete|heavy_tail|run_error' "
    "/root/mk_v2_runs/e3_b9_calib/lane_v2_0.log /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log "
    "| tail -24; echo SEP; "
    "ls -la /root/mk_v2_runs/e3_b9_calib/units/ | wc -l; "
    "ls /root/mk_v2_runs/e1/witness_confirmation/ | grep -i followup; echo NOFOLLOWUP"
)

c = _remote.connect()
print("##### SYSTEM #####")
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print("##### B9 QUEUE / LANES #####")
_, o, _ = _remote.run(c, CMD2, timeout=240, echo=False)
print(o)
print("##### RECENT UNITS #####")
_, o, _ = _remote.run(c, CMD3, timeout=120, echo=False)
c.close()
print(o)
print("DEEP_PROBE_DONE")
