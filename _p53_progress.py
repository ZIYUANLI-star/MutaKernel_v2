import _remote, glob
c = _remote.connect()
_remote.run(c, "ps -eo pid,etime,cmd | grep '_mutant_worker.*P53__const_perturb__4' | grep -v grep", timeout=30)
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import json,glob;\nfs=glob.glob('/root/mk_v2_runs/e1/e1cse_*/res_L1_P53__const_perturb__4.json');\nfs=[f for f in fs if 'cazymsn' in f] or fs;\nd=json.load(open(fs[0]));ts=d.get('trials') or [];\nfrom collections import Counter;\nprint('scratch',fs[0].split('/')[-2]);\nprint('n_trials',len(ts),'valid',d.get('valid_rounds'),'round_timeouts',d.get('round_timeouts'));\nprint('by',Counter((t.get('round_type'),t.get('status')) for t in ts));\npols=[t.get('policy') for t in ts if t.get('round_type')=='stress'];\nfrom collections import OrderedDict;\nprint('stress policies seen (unique, in order):');\nseen=[];\n[seen.append(p) for p in pols if p not in seen];\nprint(seen)\" 2>&1 | tail", timeout=30)
c.close()
