"""Smoke-test the wave-1.5 builders on small subsets (all CPU, no GPU)."""
import _remote as R

sh = r"""
set -e
cd /root/mk_v2_ops
PY=/root/miniconda3/bin/python
CAMP=/root/mk_v2_runs/e3_campaign
SMOKE=/root/mk_v2_runs/e3_campaign/wave15/_smoke
rm -rf $SMOKE && mkdir -p $SMOKE

echo '=== 0. pick 3 subject ids ==='
$PY - <<'EOF'
import json
m = json.load(open('/root/mk_v2_runs/e3_campaign/wave1_subject_manifest_v2.json'))
ids = sorted(s['subject_id'] for s in m['subjects'])
picks = [ids[0], ids[len(ids)//2], ids[-1]]
open('/root/mk_v2_runs/e3_campaign/wave15/_smoke/ids3.txt', 'w').write('\n'.join(picks) + '\n')
print(picks)
EOF

echo '=== 1. subset-manifest ==='
$PY build_wave15_lane_plans.py subset-manifest \
  --subjects $CAMP/wave1_subject_manifest_v2.json \
  --subject-ids $SMOKE/ids3.txt --out $SMOKE/manifest3.json

echo '=== 2. mdir-plan on 3 subjects ==='
$PY build_wave15_lane_plans.py mdir-plan \
  --subjects $SMOKE/manifest3.json \
  --map /root/mk_v2_runs/e1/fault_to_stress_map.json \
  --artifact-root / \
  --out $SMOKE/mdir3.json

echo '=== 3. legacy-manifest + matrix-plan on 3 subjects ==='
$PY build_wave15_lane_plans.py legacy-manifest \
  --subjects $CAMP/wave1_subject_manifest_v2.json \
  --subject-ids $SMOKE/ids3.txt --out $SMOKE/legacy3.json
$PY build_wave15_lane_plans.py matrix-plan \
  --subjects $SMOKE/legacy3.json \
  --matrix /root/mk_v2/configs/fse_e3_wave1_matrix.json \
  --strategy-names five-iid-historical-anchor mutakernel-full \
  --matrix-id wave15-lane-g-legacy-v1 \
  --out $SMOKE/legacy_plan3.json

echo '=== 4. lodo delta + full on 3 subjects ==='
$PY build_wave15_lane_plans.py lodo-plan --variant delta \
  --subjects $SMOKE/manifest3.json \
  --matrix /root/mk_v2/configs/fse_e3_wave1_matrix.json \
  --out $SMOKE/lodo_delta3.json
$PY build_wave15_lane_plans.py lodo-plan --variant full \
  --subjects $SMOKE/manifest3.json \
  --matrix /root/mk_v2/configs/fse_e3_wave1_matrix.json \
  --out $SMOKE/lodo_full3.json

echo '=== 5. subset analysis on the live (partial) lane M ledger ==='
$PY wave15_subset_analysis.py \
  --observations $CAMP/lane_m_run/observations.jsonl \
  --subjects $CAMP/wave1_subject_manifest_v2.json \
  --out-dir $SMOKE/subsets

echo '=== 6. b9 tol map (real, kept) ==='
$PY build_b9_tol_map.py --calib-dir /root/mk_v2_runs/e3_b9_calib \
  --out /root/mk_v2_runs/e3_campaign/wave15/b9_tol_map.json

echo ALL_SMOKE_OK
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2_ops/_smoke.sh", "w") as fh:
    fh.write(sh)
sftp.close()
R.run(c, "bash /root/mk_v2_ops/_smoke.sh", timeout=1800)
c.close()
print("SMOKE_DONE")
