"""Seed run5's completed.json with the 27 probes already paired in run4."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
_remote.run(c, "mkdir -p /root/mk_v2_runs/e0_run5_s0")
sftp.put("_run5_precompleted.json", "/root/mk_v2_runs/e0_run5_s0/completed.json")
sftp.close()
_remote.run(c, "wc -c /root/mk_v2_runs/e0_run5_s0/completed.json && "
               "/root/miniconda3/bin/python -c \"import json; "
               "print(len(json.load(open('/root/mk_v2_runs/e0_run5_s0/completed.json'))), 'ids seeded')\"")
c.close()
print("SEED_DONE")
