"""E3 wave-1 Lane-M build: full manifest + extended-scope matrix + plan + env.

Design decision (documented in the campaign memo): the signed L1/L2 contracts
freeze observed dims and authorize eval-mode only, so an `in_contract`-scope
plan is unconstructible for B6/M-full (protocol hard-gates at planning). Per
blueprint 5.1.1 ("A test outside the contract can never produce an in-contract
defect report; such findings are reported separately as extended-contract
observations"), the campaign plan uses experiment_scope=extended_contract,
executes the full preregistered case lists, and the scoring side classifies
every observation in/out-of-contract via assert_case_in_contract. Strategy
definitions (hence strategy_ids) are byte-identical to the v1 matrix.
"""
import json

import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"

# 1. E3 matrix variant: only matrix_id/scope/description change
m = json.load(open("configs/fse_strategy_matrix.json", encoding="utf-8"))
m["matrix_id"] = "fse-e3-wave1-extended-v1"
m["experiment_scope"] = "extended_contract"
m["description"] = (
    "E3 wave-1 campaign matrix. Identical strategies/cases/seeds to "
    "fse-rich-contract-compute-matched-v1; scope=extended_contract because "
    "the signed L1/L2 subject contracts (frozen observed dims, eval-only) "
    "do not authorize the train/config/repeated cases of dtype-mode-config "
    "and mutakernel-full, and the protocol hard-fails in_contract planning. "
    "Scoring classifies each observation against the subject contract: "
    "out-of-contract cases are reported as extended-contract observations "
    "and never as in-contract defects (blueprint 5.1.1)."
)
mat = json.dumps(m, indent=2)
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/configs/fse_e3_wave1_matrix.json", "w") as fh:
    fh.write(mat)
sftp.close()
print("matrix uploaded")

OUT = "/root/mk_v2_runs/e3_campaign"

# 2. full 653-subject manifest
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/build_fse_subject_manifest.py "
       f"--root / --input {OUT}/wave1_manifest_input.jsonl "
       f"--output {OUT}/wave1_subject_manifest.json", timeout=900)
if code != 0:
    raise SystemExit("manifest build failed")

# 3. campaign plan (immutable, content-addressed)
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/plan_fse_experiment.py "
       f"--subjects {OUT}/wave1_subject_manifest.json "
       "--strategy-matrix configs/fse_e3_wave1_matrix.json "
       f"--output {OUT}/wave1_lane_m_plan.json", timeout=1800)
if code != 0:
    raise SystemExit("plan build failed")

# 4. environment manifest
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/capture_fse_environment.py "
       f"--output {OUT}/wave1_environment.json", timeout=600)
if code != 0:
    raise SystemExit("environment capture failed")

# 5. summary
R.run(c, f"{P} -c \"import json;"
         f"p=json.load(open('{OUT}/wave1_lane_m_plan.json'));"
         "print('plan_sha256', p['plan_sha256'][:16]);"
         "print('subjects', p['subject_count']);"
         "print('strategies', p['strategy_count']);"
         "print('test_cases', p['test_case_count']);"
         "print('scope', p['experiment_scope'])\"", timeout=120)
R.run(c, f"ls -la {OUT}/", timeout=60)
c.close()
print("LANE_M_BUILD_DONE")
