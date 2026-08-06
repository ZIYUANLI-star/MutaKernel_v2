import _remote

c = _remote.connect()
_remote.run(c,
    "cd /root/mk_v2 && /root/miniconda3/bin/python -u "
    "/root/mk_v2/_final_window_go.py --dry-run 2>&1 | tail -50",
    timeout=300)
c.close()
print("P37_DRYRUN_DONE")
