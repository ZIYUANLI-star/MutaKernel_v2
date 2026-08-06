import _remote

c = _remote.connect()
_remote.run(c, (
    "ps -o pid,ppid,lstart,cmd -p 265320 | cat; "
    "echo ---PARENT---; ps -o pid,cmd -p $(ps -o ppid= -p 265320 | tr -d ' ') | cat"
), timeout=60)
_remote.run(c, (
    "kill -9 265320 && echo KILLED_265320; sleep 3; "
    "ps aux | grep '_mutant_[w]orker' | awk '{print $2, $12}'; "
    "echo ---GPU---; nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader"
), timeout=60)
c.close()
