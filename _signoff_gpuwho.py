import _remote

c = _remote.connect()
_remote.run(c, (
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
    "echo ---; "
    "for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do "
    "echo \"== $p\"; ps -o pid,ppid,etime,cmd -p $p | tail -1; done"
), timeout=60)
c.close()
