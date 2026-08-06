import _remote

c = _remote.connect()
CMDS = [
    "ls /root/mk_v2/external/C6_gpuemu/ | head; echo ---; "
    "find /root/mk_v2/external/C6_gpuemu -maxdepth 2 -type d | head -20",
    "/root/miniconda3/bin/python /root/mk_v2/scripts/run_e3_external.py c6 "
    "--corpus-root /root/mk_v2/external/C6_gpuemu --out-dir /tmp/e3_c6_check --dry-run 2>&1 | tail -25",
    "cat /root/mk_v2_runs/e3_c6/c6_task_table.json 2>/dev/null | head -50",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    print(o)
    if e.strip():
        print('STDERR:', e[:400])
    print('=====')
c.close()
print('DONE')
