"""Morning verification: WCFU_DONE summary, fix wave outcome, wcfu2 status."""
import _remote

CMD1 = (
    "date '+NOW=%F %T'; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/WCFU_DONE 2>/dev/null; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/WCFU2_DONE 2>/dev/null; "
    "cat /root/mk_v2_runs/e3_b9_calib/WCFU2_BLOCKED 2>/dev/null; echo SEP; "
    "tail -n 8 /root/mk_v2_runs/e3_b9_calib/wcfu2_chain.log 2>/dev/null; echo SEP; "
    "tail -n 4 /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log"
)

CMD2 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "from collections import Counter\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "print('wave', qs['wave'], '| done', len(qs['done']), '| pending', len(qs['pending']), '| claimed', len(qs.get('claimed', {})))\n"
    "print('overall:', dict(Counter(qs['done'].values())))\n"
    "m = json.load(open('/root/mk_v2_runs/e3_b9_calib/wcfu_fp16_requeue_manifest.json'))\n"
    "fixed = Counter(qs['done'].get(u) for u in m['units'])\n"
    "print('fix-wave units (%d):' % len(m['units']), dict(fixed))\n"
    "fp16_all = [u for u in qs['done'] if 'float16' in u]\n"
    "print('all fp16 (%d):' % len(fp16_all), dict(Counter(qs['done'][u] for u in fp16_all)))\n"
    "fp32_all = [u for u in qs['done'] if 'float32' in u]\n"
    "print('all fp32 (%d):' % len(fp32_all), dict(Counter(qs['done'][u] for u in fp32_all)))\n"
    "EOF\n"
)

CMD3 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "j = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "print('generated_at:', j['generated_at'])\n"
    "print('verdict_counts:', json.dumps(j['verdict_counts']))\n"
    "print('final_counts:', json.dumps(j['final_counts']))\n"
    "print('controls:', json.dumps(j['control_cell_states']))\n"
    "for k, x in (j['verdicts'].items() if isinstance(j['verdicts'], dict) else enumerate(j['verdicts'])):\n"
    "    if isinstance(x, dict) and x.get('verdict') not in ('CONFIRMED', 'OUT_OF_SCOPE_NON_NUMERIC'):\n"
    "        print(' ', x.get('verdict'), x.get('stage'), x.get('probe_id'))\n"
    "EOF\n"
    "echo SEP; "
    "grep oom_kill /sys/fs/cgroup/memory/memory.oom_control; "
    "grep -hcE 'run_error' /root/mk_v2_runs/e3_b9_calib/lane_v2_*.log | paste -sd+ | bc; "
    "nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l; "
    "tail -c 200 /root/mk_v2_runs/e1_sentinel.log"
)

c = _remote.connect()
print('##### markers & chains #####')
_, o, _ = _remote.run(c, CMD1, timeout=90, echo=False)
print(o)
print('##### fix wave outcome #####')
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
print(o)
print('##### report & health #####')
_, o, _ = _remote.run(c, CMD3, timeout=120, echo=False)
c.close()
print(o)
print('MORNING3_DONE')
