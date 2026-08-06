import _remote
c = _remote.connect()
R = _remote.run
script = r'''
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
'''
open("_wc5_tmp.py","w").write(script)
sftp = c.open_sftp()
sftp.put("_wc5_tmp.py", "/root/mk_v2/_wc5_tmp.py")
sftp.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc5_tmp.py", timeout=300)
c.close()
print("DONE")
