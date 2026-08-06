import _remote

DIAG = r"""
import glob
import json

for path in sorted(glob.glob("/root/mk_v2_runs/e1/cse_observations_lane[345].jsonl")):
    lane = path.rsplit("lane", 1)[-1].split(".")[0]
    for l in open(path):
        r = json.loads(l)
        tr = r.get("trials") or []
        nrand = sum(1 for t in tr if t.get("round_type") == "random"
                    and t.get("status") in ("passed", "survived", "ok"))
        nstr = sum(1 for t in tr if t.get("round_type") == "stress"
                   and t.get("status") in ("passed", "survived", "ok"))
        vr = r.get("valid_rounds")
        print(f"lane{lane} {r['probe_id'][:44]:<44} out={r['outcome'][:12]:<12} "
              f"wall={r.get('wall_ms',0)/1000:.0f}s timed_out={r.get('timed_out')} "
              f"valid_rounds={vr} rand_ok={nrand} stress_ok={nstr} ntrials={len(tr)}")
print("INC_DIAG_DONE")
"""

c = _remote.connect()
s = c.open_sftp()
with s.open("/root/mk_v2/_cse_inc_diag.py", "w") as f:
    f.write(DIAG)
s.close()
_, out, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_cse_inc_diag.py 2>&1",
                        timeout=180, echo=False)
c.close()
print(out)
