"""M-dir pre-flight: build per-subject directed plans for all 653 wave-1
subjects against the FROZEN map (CPU-only, static fingerprint, no execution).

PRELIMINARY: contracts are drafted but not yet dual-signed, so no contract
gate is applied here.  Purpose: (a) validate every candidate parses and
fingerprints, (b) exercise the full map->plan path at campaign scale,
(c) surface per-subject directed/general splits.  Final plans MUST be rebuilt
with signed contracts (the output manifest says so).
"""
import _remote as R

c = R.connect()

# ensure builder script is current on remote
sftp = c.open_sftp()
sftp.put("scripts/build_mdir_strategy_row.py",
         "/root/mk_v2/scripts/build_mdir_strategy_row.py")
sftp.close()

subjects_py = r"""
import json
from pathlib import Path

out = open("/root/mk_v2_runs/e3_campaign/wave1_subjects.jsonl", "w")
n = 0
for corpus in ("c3_wave1", "c5_wave1"):
    reg = json.load(open(f"/root/mk_v2_runs/e3_corpora/{corpus}/registry.json"))
    for s in reg["subjects"]:
        sid = s["stable_id"]
        out.write(json.dumps({
            "subject_id": f"{reg['corpus']}__{s['task_key']}__{sid[:16]}",
            "stable_id": sid,
            "task_key": s["task_key"],
            "corpus": reg["corpus"],
            "candidate_path":
                f"/root/mk_v2_runs/e3_corpora/{corpus}/candidates/{sid}.py",
        }) + "\n")
        n += 1
out.close()
print("subjects.jsonl rows:", n)
"""
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_mk_subjects.py", "w") as fh:
    fh.write(subjects_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _mk_subjects.py",
      timeout=120)

code, o, e = R.run(
    c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -u "
       "scripts/build_mdir_strategy_row.py "
       "--map /root/mk_v2_runs/e3_campaign/fault_to_stress_map_frozen.json "
       "--subjects /root/mk_v2_runs/e3_campaign/wave1_subjects.jsonl "
       "--out-dir /root/mk_v2_runs/e3_campaign/mdir_preflight "
       "2>&1 | tail -12",
    timeout=1800)

# tag the output as preliminary (no contract gate yet)
R.run(c, "/root/miniconda3/bin/python -c \"import json;"
         "p='/root/mk_v2_runs/e3_campaign/mdir_preflight/mdir_strategy_row.json';"
         "d=json.load(open(p));"
         "d['status']='PRELIMINARY_NO_CONTRACT_GATE';"
         "d['rebuild_required']='rebuild with dual-signed contracts before any "
         "scored run; map_sha256 must match map_freeze_manifest.json';"
         "json.dump(d, open(p,'w'), indent=2);"
         "print('tagged', d['status'], 'subjects', len(d['subjects']))\"",
      timeout=60)
c.close()
print("MDIR_PREFLIGHT_DONE")
