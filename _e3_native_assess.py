import _remote

c = _remote.connect()
CMDS = [
    # C6 corpus + native repro tooling
    "ls /root/mk_v2_runs/e3_c6/ 2>/dev/null | head -20; echo ---; "
    "ls /root/mk_v2/external/ 2>/dev/null; echo ---; "
    "grep -rn 'native' /root/mk_v2/configs/external_baselines.json | head -10",
    # what does run_e3_external support?
    "/root/miniconda3/bin/python /root/mk_v2/scripts/run_e3_external.py --help 2>&1 | head -40",
    # C6 definition
    "grep -rn 'C6\\|c6' /root/mk_v2/configs/external_baselines.json | head; echo ---; "
    "ls /root/mk_v2/scripts/ | grep -i 'c6\\|native\\|repro'",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o)
    if e.strip():
        print('STDERR:', e[:300])
    print('=====')
c.close()
print('DONE')
