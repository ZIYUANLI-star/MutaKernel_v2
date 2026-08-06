import _remote
c = _remote.connect()
print("=== lane3 driver+worker ===")
_remote.run(c, "ps -eo pid,etime,cmd | grep -E 'lane 3|_mutant_worker.*P53' | grep -v grep", timeout=30)
print("=== const_perturb__4 partial result ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import json,glob;\nfs=glob.glob('/root/mk_v2_runs/e1/e1cse_*/res_L1_P53__const_perturb__4.json');\nprint('files',fs);\nd=json.load(open(fs[0])) if fs else {};\nts=d.get('trials') or [];\nfrom collections import Counter;\nprint('n_trials',len(ts),'valid',d.get('valid_rounds'),'round_timeouts',d.get('round_timeouts'),'partial',d.get('partial'));\nprint('by',Counter((t.get('round_type'),t.get('status')) for t in ts));\nprint('last6',[(t.get('policy'),t.get('status'),t.get('round_timeout')) for t in ts[-6:]])\" 2>&1 | tail", timeout=30)
c.close()
