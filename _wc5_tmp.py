
import json, glob, collections
p = "/root/mk_v2_runs/e1/cse_observations_lane1.jsonl"
n = 0
for line in open(p):
    r = json.loads(line)
    n += 1
    if n <= 2:
        print(json.dumps(r, indent=1, ensure_ascii=False)[:3000])
        print("-----")
print("lane1 rows", n)
p2 = "/root/mk_v2_runs/e1/equiv_observations.jsonl"
n=0
for line in open(p2):
    r = json.loads(line); n+=1
    if n<=1:
        print("EQUIV SAMPLE:", json.dumps(r, indent=1, ensure_ascii=False)[:3000])
print("equiv rows", n)
