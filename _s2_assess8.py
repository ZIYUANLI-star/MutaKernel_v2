import _remote

c = _remote.connect()
CMDS = [
    "head -30 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.sh",
    # how did wcfu requeue the fp16 units? (queue mutation precedent)
    "grep -n 'stage2\\|pending\\|queue_state\\|DONE_LANE' /root/mk_v2/_wcfu_chain.py | head -30",
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "m = json.load(open('/root/mk_v2_runs/e3_b9_calib/wcfu_fp16_requeue_manifest.json'))\n"
    "print(json.dumps(m, indent=1)[:1200])\n"
    "EOF\n",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o)
    if e.strip():
        print('STDERR:', e[:300])
    print('=====')
c.close()
print('DONE')
