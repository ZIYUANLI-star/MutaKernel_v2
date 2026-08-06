#!/usr/bin/env python3
import json

import _remote

c = _remote.connect()
r = lambda cmd, t=120: _remote.run(c, cmd, timeout=t)
r("/root/miniconda3/bin/python - <<'EOF'\n"
  "import json\n"
  "for lane in (3, 5):\n"
  "    done = json.load(open(f'/root/mk_v2_runs/e1/cse_completed_lane{lane}.json'))\n"
  "    recs = [json.loads(x) for x in open(f'/root/mk_v2_runs/e1/cse_observations_lane{lane}.jsonl')]\n"
  "    inc = [x['probe_id'] for x in recs if x['outcome'] == 'INCONCLUSIVE']\n"
  "    v2 = [x for x in recs if x.get('input_pipeline') == 'cse_gen_opt_v2']\n"
  "    walls = sorted(round(x['wall_ms']/1000) for x in v2)\n"
  "    print(f'lane{lane}: completed={len(done)} obs={len(recs)} inc={len(inc)} v2_records={len(v2)} v2_walls={walls}')\n"
  "    print('  inc ids:', inc)\n"
  "kernels3 = {}\n"
  "plan = json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))\n"
  "print('lane3 kernel order:', plan['lanes'][3]['kernels'])\n"
  "print('lane5 kernel order:', plan['lanes'][5]['kernels'])\n"
  "EOF")
r("tail -n 3 /root/mk_v2_runs/e1_cse_lane3.log; echo ---; "
  "tail -n 3 /root/mk_v2_runs/e1_cse_lane5.log")
c.close()
print("FINAL_CHECK_DONE")
