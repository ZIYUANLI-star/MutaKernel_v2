import _remote
c = _remote.connect()
print("=== new const_perturb__4 cfg: stress_policies (should EXCLUDE the 3) ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import json;d=json.load(open('/root/mk_v2_runs/e1/e1cse_cazymsn_/cfg_L1_P53__const_perturb__4.json'));sp=d['stress_policies'];print('n_policies',len(sp));print('has mixed_extremes',' mixed_extremes' in sp or 'mixed_extremes' in sp);print('excluded ok:', all(x not in sp for x in ['mixed_extremes','sparse','sparse_extreme']));print(sp)\"", timeout=30)
print("=== completed_lane3 ledger + count ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import json;d=json.load(open('/root/mk_v2_runs/e1/cse_completed_lane3.json'));print('n_done',len(d));import re;print('P53 done:',[x for x in d if 'P53' in x]);print('const_perturb__4 in ledger:', 'L1_P53__const_perturb__4' in d)\"", timeout=30)
print("=== all lane3 INCONCLUSIVE observations ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import json;rows=[json.loads(l) for l in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl')];inc=[r for r in rows if r['outcome']=='INCONCLUSIVE'];print('total obs',len(rows),'INCONCLUSIVE',len(inc));[print(' ',r['probe_id'],round(r.get('wall_ms',0)/1000,1),'s',r.get('inconclusive_class'),'timed_out',r.get('timed_out')) for r in inc]\"", timeout=30)
c.close()
