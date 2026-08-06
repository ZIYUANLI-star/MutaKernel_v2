import _remote

c = _remote.connect()
print("===== go-script precondition dry-run (must ABORT now) =====")
_remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_cse_split_go.py; echo exit=$?", timeout=60)
print("===== plan lanes count =====")
_remote.run(c, "/root/miniconda3/bin/python -c \"import json; p=json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json')); print('lanes:', len(p['lanes']), 'version:', p.get('version'))\"", timeout=30)
c.close()
print("DRYRUN_DONE")
