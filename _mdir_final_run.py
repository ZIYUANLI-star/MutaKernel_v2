"""Rebuild M-dir per-subject plans WITH the signed contract gate (final).

Joins wave1_subjects.jsonl with contracts_c2c3c5_signed_v1.jsonl by task_key,
runs build_mdir_strategy_row.py against the frozen map, and verifies the
map digest in the output equals map_freeze_manifest.json.
"""
import _remote as R

join_py = r"""
import json
contracts = {}
for line in open("/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_signed_v1.jsonl",
                 encoding="utf-8"):
    r = json.loads(line)
    contracts[r["task_key"]] = r["contract"]
print("signed contracts:", len(contracts))

out = open("/root/mk_v2_runs/e3_campaign/wave1_subjects_signed.jsonl", "w")
n, miss = 0, []
for line in open("/root/mk_v2_runs/e3_campaign/wave1_subjects.jsonl",
                 encoding="utf-8"):
    s = json.loads(line)
    ct = contracts.get(s["task_key"])
    if ct is None:
        miss.append(s["task_key"]); continue
    s["contract"] = ct
    out.write(json.dumps(s) + "\n")
    n += 1
out.close()
print("subjects with contracts:", n, "missing:", sorted(set(miss)))
assert not miss, "missing contracts"
"""

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_mk_subjects_signed.py", "w") as fh:
    fh.write(join_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _mk_subjects_signed.py",
      timeout=300)
code, o, e = R.run(
    c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
       "scripts/build_mdir_strategy_row.py "
       "--map /root/mk_v2_runs/e3_campaign/fault_to_stress_map_frozen.json "
       "--subjects /root/mk_v2_runs/e3_campaign/wave1_subjects_signed.jsonl "
       "--out-dir /root/mk_v2_runs/e3_campaign/mdir_final "
       "2>&1 | tail -6",
    timeout=2400)
if code != 0:
    raise SystemExit("mdir final build failed")

R.run(c, "/root/miniconda3/bin/python -c \"import json;"
         "row=json.load(open('/root/mk_v2_runs/e3_campaign/mdir_final/mdir_strategy_row.json'));"
         "fz=json.load(open('/root/mk_v2_runs/e3_campaign/map_freeze_manifest.json'));"
         "ok=row['map']['sha256']==fz['map_sha256'];"
         "skipped=sum(s['skipped_unauthorized'] for s in row['subjects']);"
         "print('map_digest_match', ok, 'subjects', len(row['subjects']),"
         " 'total_skipped_unauthorized', skipped)\"", timeout=60)
c.close()
print("MDIR_FINAL_DONE")
