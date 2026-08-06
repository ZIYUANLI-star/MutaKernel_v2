"""Pull regrade plan + verdicts, and locate dtype application code."""
import _remote

CMD1 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "j = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "print('verdict_counts:', json.dumps(j['verdict_counts'], ensure_ascii=False))\n"
    "print('final_counts:', json.dumps(j['final_counts'], ensure_ascii=False))\n"
    "print('nondet kernels:', json.dumps(j['nondeterministic_kernels'], ensure_ascii=False))\n"
    "print('cse before/after:', j['cse_fault_classes_before'], j['cse_fault_classes_after'])\n"
    "print('equiv before/after:', j['equiv_fault_classes_before'], j['equiv_fault_classes_after'])\n"
    "print()\n"
    "print('REGRADE PLAN:')\n"
    "print(json.dumps(j['regrade_plan'], ensure_ascii=False, indent=1)[:4000])\n"
    "print()\n"
    "print('NON-CONFIRMED VERDICTS:')\n"
    "for k, x in j['verdicts'].items():\n"
    "    if isinstance(x, dict) and x.get('verdict') != 'CONFIRMED':\n"
    "        print(' ', x.get('verdict'), k, json.dumps({a: x.get(a) for a in ('stage','position','flake','notes','replays_hit','first_hit') if x.get(a) is not None}, ensure_ascii=False)[:200])\n"
    "EOF\n"
)

CMD2 = (
    "grep -rn 'dtype' /root/mk_v2/scripts/run_e3_external.py | head -15; echo SEP; "
    "grep -rn 'float16\\|dtype' /root/mk_v2/_b9_calib_prep.py | head -25; echo SEP; "
    "grep -rln 'to(dtype\\|\\.half()\\|torch.float16' /root/mk_v2/mutakernel/ /root/mk_v2/scripts/ 2>/dev/null | head; echo SEP; "
    "grep -rn 'float16\\|\\.half()' $(grep -rln 'b9_uniform10' /root/mk_v2/mutakernel/ /root/mk_v2/scripts/ 2>/dev/null | head -3) 2>/dev/null | head -20"
)

c = _remote.connect()
print('##### REGRADE / VERDICTS #####')
_, o, _ = _remote.run(c, CMD1, timeout=120, echo=False)
print(o)
print('##### DTYPE CODE #####')
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
c.close()
print(o)
print('ADV_INSPECT2_DONE')
