"""Dump full records for fp16 controls_incomplete units."""
import _remote

CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "base = '/root/mk_v2_runs/e3_b9_calib/units/'\n"
    "p = base + 'L2_P14__float16/b9_L2_P14_observations.jsonl'\n"
    "recs = [json.loads(l) for l in open(p) if l.strip()]\n"
    "print('FULL FIRST RECORD:')\n"
    "print(json.dumps(recs[0], ensure_ascii=False, indent=1)[:2000])\n"
    "print()\n"
    "print('SUMMARY:')\n"
    "print(json.dumps(json.load(open(base + 'L2_P14__float16/b9_L2_P14_summary.json')), ensure_ascii=False, indent=1)[:2000])\n"
    "print()\n"
    "print('SUMMARY of a calibrated_ok fp16 for contrast (find one):')\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "ok16 = [u for u, s in qs['done'].items() if s == 'calibrated_ok' and 'float16' in u][:3]\n"
    "print('examples ok fp16:', ok16)\n"
    "# distribution: which L-level are the ok fp16?\n"
    "print('ok fp16 by level:', {lvl: sum(1 for u in ok16v if u.startswith(lvl)) for ok16v in [[u for u, s in qs['done'].items() if s=='calibrated_ok' and 'float16' in u]] for lvl in ('L1','L2')})\n"
    "print('inc fp16 by level:', {lvl: sum(1 for u in inc if u.startswith(lvl)) for inc in [[u for u, s in qs['done'].items() if s=='controls_incomplete' and 'float16' in u]] for lvl in ('L1','L2')})\n"
    "EOF\n"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=180, echo=False)
c.close()
print(o)
print("DONE2")
