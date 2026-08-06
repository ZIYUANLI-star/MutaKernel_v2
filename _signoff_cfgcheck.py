import _remote

c = _remote.connect()
_remote.run(c, (
    "ls -dt /root/mk_v2_runs/e1/e1cse_* 2>/dev/null | head -3; "
    "echo ---CFG---; "
    "d=$(ls -dt /root/mk_v2_runs/e1/e1cse_* | head -1); ls -la $d; "
    "for f in $d/cfg_*.json; do "
    "/root/miniconda3/bin/python -c \"import json,sys; c=json.load(open('$f')); "
    "print('$f', 'round_timeout=', c.get('round_timeout'), 'id=', c.get('mutant_id'))\"; done; "
    "echo ---PS---; ps aux | grep 'signoff_[r]equeue' | head -3; "
    "echo ---LOG---; tail -3 /root/mk_v2_runs/e1_cse_lane3_signoff_requeue.log"
), timeout=120)
c.close()
