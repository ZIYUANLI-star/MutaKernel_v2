import json
import _remote as R

c = R.connect()
sftp = c.open_sftp()
sftp.get("/root/mk_v2/configs/fse_strategy_matrix.json", "_remote_src/fse_strategy_matrix.json")
sftp.get("/root/mk_v2_runs/e1/fault_to_stress_map.json", "_remote_src/fault_to_stress_map.json")
sftp.close()

print("### map provenance: mtime + any freeze record")
R.run(c, "stat -c '%y %s %n' /root/mk_v2_runs/e1/fault_to_stress_map.json; "
         "grep -rl 'fault_to_stress_map' /root/mk_v2_runs/e3_campaign/*.json 2>/dev/null; "
         "grep -rn 'map_sha256\\|fault_to_stress' /root/mk_v2_runs/e1/*.json 2>/dev/null | head -5; "
         "ls -la /root/mk_v2_runs/e1/ | grep -i 'map\\|freeze' ", timeout=60)
print("### lane M ignition time")
R.run(c, "head -c 400 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | python3 -c \"import sys,json; r=json.loads(sys.stdin.readline()); print({k:r[k] for k in r if 'time' in k.lower() or 'at' in k.lower()})\" 2>/dev/null || head -1 /root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl | cut -c1-600", timeout=60)
c.close()
print("DONE")
