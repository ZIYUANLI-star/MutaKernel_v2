"""Verify wcfu2 outcome: final verdicts after control top-up."""
import _remote

CMD = (
    "cat /root/mk_v2_runs/e3_b9_calib/WCFU2_DONE; echo SEP; "
    "tail -n 6 /root/mk_v2_runs/e3_b9_calib/wcfu2_chain.log; echo SEP; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "j = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "print('generated_at:', j['generated_at'])\n"
    "for k, x in (j['verdicts'].items() if isinstance(j['verdicts'], dict) else enumerate(j['verdicts'])):\n"
    "    if isinstance(x, dict) and x.get('verdict') not in ('CONFIRMED', 'OUT_OF_SCOPE_NON_NUMERIC'):\n"
    "        print(' ', x.get('verdict'), x.get('stage'), x.get('probe_id'))\n"
    "print('regrade entries:', len(j.get('regrade_plan', [])))\n"
    "for r in j.get('regrade_plan', []):\n"
    "    print(' ', r['stage'], r['probe_id'], '->', r['regrade'])\n"
    "EOF\n"
    "echo SEP; "
    "/root/miniconda3/bin/python /root/mk_v2/_b9_brake.py status 2>&1 | head -6; "
    "nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=120, echo=False)
c.close()
print(o)
print('WCFU2_FINAL_DONE')
