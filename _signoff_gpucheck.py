import _remote

c = _remote.connect()
_remote.run(c, (
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
    "echo ---WORKERS---; ps aux | grep '_mutant_[w]orker' | head -5; "
    "echo ---DIRS---; ls -ldt --time-style=+%H:%M /root/mk_v2_runs/e1/e1cse_* | head -4; "
    "echo ---NEWSCRATCH---; "
    "for d in $(ls -dt /root/mk_v2_runs/e1/e1cse_* | head -3); do echo $d; ls -la --time-style=+%H:%M $d | tail -3; done"
), timeout=60)
c.close()
