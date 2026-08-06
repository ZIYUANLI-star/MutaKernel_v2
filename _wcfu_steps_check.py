"""Pull wcfu steps 5-8 detail + regenerated verdicts + fix wave startup."""
import _remote

CMD1 = "awk '/step 5|step 6|step 7|canary|step 8|step 9|requeued/' /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log | tail -15"

CMD2 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "j = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "print('generated_at:', j['generated_at'])\n"
    "print('verdict_counts:', json.dumps(j['verdict_counts']))\n"
    "print('final_counts:', json.dumps(j['final_counts']))\n"
    "print('control_cell_states:', json.dumps(j['control_cell_states']))\n"
    "print('nondet:', j['nondeterministic_kernels'])\n"
    "print()\n"
    "for k, x in (j['verdicts'].items() if isinstance(j['verdicts'], dict) else enumerate(j['verdicts'])):\n"
    "    if isinstance(x, dict) and x.get('verdict') not in ('CONFIRMED', 'OUT_OF_SCOPE_NON_NUMERIC'):\n"
    "        print(x.get('verdict'), '|', x.get('stage'), x.get('probe_id'))\n"
    "print()\n"
    "m = json.load(open('/root/mk_v2_runs/e3_b9_calib/wcfu_fp16_requeue_manifest.json'))\n"
    "print('fp16 requeue units:', len(m['units']))\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "print('wave', qs['wave'], '| done', len(qs['done']), '| pending', len(qs['pending']), '| claimed', len(qs.get('claimed', {})))\n"
    "EOF\n"
)

CMD3 = (
    "pgrep -af '[_]b9_calib_driver_v2' | head -4; echo SEP; "
    "tail -n 4 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo '---'; "
    "tail -n 4 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log; echo SEP; "
    "cat /root/mk_v2_runs/e3_b9_calib/wcfu_canary/b9_L2_P14_summary.json 2>/dev/null | head -c 400"
)

c = _remote.connect()
print('##### chain steps #####')
_, o, _ = _remote.run(c, CMD1, timeout=60, echo=False)
print(o)
print('##### new report #####')
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
print(o)
print('##### fix wave startup #####')
_, o, _ = _remote.run(c, CMD3, timeout=60, echo=False)
c.close()
print(o)
print('STEPS_CHECK_DONE')
