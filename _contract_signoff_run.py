"""Execute the L1/L2 contract dual-review sign-off (delegated to agent).

Review basis: 契约双人审核底稿_L1L2_200.md (auto pre-review: 198/200 clean,
2 outliers).  Decisions recorded here and in the signed batch:
  * Clusters 1-5: ACCEPT DEFAULTS for the three human-pending clauses
    (determinism=True, value_domain=unrestricted_finite, variable dims frozen
    to observed get_inputs() sizes) — identical to the E1 protocol already
    validated over 607 probes.
  * L1_P93 (bool dtype), L1_P95 (int64 dtype): AMEND — integer/bool tensors
    compare exactly; add dtype_tolerances entries atol=0.0, rtol=0.0 and bump
    contract_id -auto-v1 -> -signed-v2.
Provenance: review performed by the automation agent under explicit user
delegation (user instruction 2026-08-01 17:41 '任何需要人工来进行的任务，
你先作为人工进行'); pass A = rule-based pre-review, pass B = agent
adjudication.  Recorded in every row and the freeze manifest.

Then: re-freeze (draft=false), place CONTRACTS_FROZEN marker, fetch artifacts
back to the local archive.
"""
import os

import _remote as R

sign_py = r'''
import hashlib, json, sys
from datetime import datetime, timezone
sys.path.insert(0, "/root/mk_v2")
from src.experiments.contract import validate_contract

SRC = "/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft.jsonl"
OUT = "/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_signed_v1.jsonl"
NOW = datetime.now(timezone.utc).isoformat()

REVIEW = {
    "signed_at": NOW,
    "worksheet": "契约双人审核底稿_L1L2_200.md",
    "pass_a": "scripts/contract_prereview.py rule-based pre-review "
              "(hash/schema/tolerance-coverage/binding-bounds/source-hash; "
              "198/200 clean)",
    "pass_b": "agent adjudication under explicit user delegation "
              "(2026-08-01 17:41)",
    "cluster_decisions": "clusters 1-5: accept defaults for determinism/"
                         "value_domain/variable_dimensions (matches the E1 "
                         "protocol validated over 607 probes)",
    "amendments": {
        "L1_P93": "add dtype_tolerances.bool={atol:0,rtol:0} (exact compare)",
        "L1_P95": "add dtype_tolerances.int64={atol:0,rtol:0} (exact compare)",
    },
}

AMEND = {"L1_P93": "bool", "L1_P95": "int64"}

rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
assert len(rows) == 200, len(rows)
n_amended = 0
for r in rows:
    tid = r["task_id"]
    c = r["contract"]
    if tid in AMEND:
        dt = AMEND[tid]
        tols = c["oracle"]["dtype_tolerances"]
        assert dt not in tols, (tid, dt)
        tols[dt] = {"atol": 0.0, "rtol": 0.0}
        assert c["contract_id"].endswith("-auto-v1"), c["contract_id"]
        c["contract_id"] = c["contract_id"].replace("-auto-v1", "-signed-v2")
        r["amendment_log"] = [{
            "at": NOW, "change": "dtype_tolerances.%s = {atol:0, rtol:0}" % dt,
            "reason": "integer/bool outputs compare exactly; pre-review "
                      "MISSING_DTYPE_TOL outlier resolved",
        }]
        n_amended += 1
    validate_contract(c)
    blob = json.dumps(c, sort_keys=True, separators=(",", ":"))
    r["contract_sha256"] = hashlib.sha256(blob.encode()).hexdigest()
    r["extraction"]["human_review_pending"] = []
    r["review"] = REVIEW

with open(OUT, "w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, sort_keys=True) + "\n")

batch = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
freeze = {
    "created_at": NOW,
    "contracts": 200,
    "draft": False,
    "amended": n_amended,
    "batch_sha256": batch,
    "source_draft": SRC,
    "review": REVIEW,
}
json.dump(freeze, open(OUT.replace(".jsonl", ".freeze.json"), "w"), indent=2)

marker = {
    "frozen_at": NOW,
    "batch": OUT,
    "batch_sha256": batch,
    "note": "E3 wave-1 may fire; observations before this marker are invalid",
}
json.dump(marker, open("/root/mk_v2_runs/e3_campaign/CONTRACTS_FROZEN", "w"),
          indent=2)
print("SIGNED contracts=200 amended=%d batch_sha256=%s" % (n_amended, batch))
'''

c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_contract_sign.py", "w") as fh:
    fh.write(sign_py)
sftp.close()
code, o, e = R.run(
    c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
       "_contract_sign.py", timeout=600)
if code != 0:
    raise SystemExit("sign-off failed")

# fetch signed artifacts to the local archive
sftp = c.open_sftp()
loc = os.path.join("MutakernelV2", "实验", "补充实验数据", "contracts")
for name in ("contracts_c2c3c5_signed_v1.jsonl",
             "contracts_c2c3c5_signed_v1.freeze.json"):
    sftp.get("/root/mk_v2_runs/e2_reconcile/" + name, os.path.join(loc, name))
    print("fetched", name)
sftp.close()
c.close()
print("CONTRACT_SIGNOFF_DONE")
