"""Inspect why recent L2 fp16 units are controls_incomplete."""
import _remote

CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob, os\n"
    "from collections import Counter\n"
    "base = '/root/mk_v2_runs/e3_b9_calib/units/'\n"
    "targets = ['L2_P14__float16', 'L2_P22__float16', 'L2_P6__float16', 'L1_P86__float16']\n"
    "for t in targets:\n"
    "    d = base + t\n"
    "    print('==', t)\n"
    "    for f in sorted(glob.glob(d + '/*.json')):\n"
    "        print('  file:', os.path.basename(f))\n"
    "    for name in ('summary.json', 'calibration.json', 'result.json'):\n"
    "        p = os.path.join(d, name)\n"
    "        if os.path.exists(p):\n"
    "            j = json.load(open(p))\n"
    "            print('  ', name, json.dumps(j, ensure_ascii=False)[:600])\n"
    "    for p in glob.glob(d + '/*observations*.jsonl'):\n"
    "        recs = [json.loads(l) for l in open(p) if l.strip()]\n"
    "        kinds = Counter()\n"
    "        for r in recs:\n"
    "            k = (r.get('outcome_kind') or r.get('status') or r.get('outcome') or '?')\n"
    "            kinds[k] += 1\n"
    "        print('  obs', os.path.basename(p), len(recs), dict(kinds))\n"
    "        if recs:\n"
    "            r0 = recs[0]\n"
    "            keep = {k: r0.get(k) for k in ('case_id','outcome_kind','status','error','max_abs','has_inf','has_nan','note','detail') if k in r0}\n"
    "            print('  first rec:', json.dumps(keep, ensure_ascii=False)[:500])\n"
    "# tally controls_incomplete by fp16/fp32 overall\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "ci = [u for u, s in qs['done'].items() if s == 'controls_incomplete']\n"
    "print('controls_incomplete total', len(ci))\n"
    "print(' fp16:', sum(1 for u in ci if 'float16' in u), ' fp32:', sum(1 for u in ci if 'float32' in u))\n"
    "ok = [u for u, s in qs['done'].items() if s == 'calibrated_ok']\n"
    "print('calibrated_ok fp16:', sum(1 for u in ok if 'float16' in u), ' fp32:', sum(1 for u in ok if 'float32' in u))\n"
    "EOF\n"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=240, echo=False)
c.close()
print(o)
print("FP16_CHECK_DONE")
