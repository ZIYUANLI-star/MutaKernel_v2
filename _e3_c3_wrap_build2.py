"""Upload + run the C3 wrapper generator, rebuild manifest/plan v2 + env."""
import _remote as R

c = R.connect()
P = "/root/miniconda3/bin/python"
OUT = "/root/mk_v2_runs/e3_campaign"

sftp = c.open_sftp()
sftp.put("_e3_c3wrap_src.py", "/root/mk_v2/_e3_c3wrap.py")
sftp.close()
code, o, e = R.run(c, f"cd /root/mk_v2 && {P} -u _e3_c3wrap.py", timeout=1200)
if code != 0:
    raise SystemExit("wrapper generation failed")

code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/build_fse_subject_manifest.py "
       f"--root / --input {OUT}/wave1_manifest_input.jsonl "
       f"--output {OUT}/wave1_subject_manifest_v2.json", timeout=900)
if code != 0:
    raise SystemExit("manifest v2 failed")
code, o, e = R.run(
    c, f"cd /root/mk_v2 && {P} -u scripts/plan_fse_experiment.py "
       f"--subjects {OUT}/wave1_subject_manifest_v2.json "
       "--strategy-matrix configs/fse_e3_wave1_matrix.json "
       f"--output {OUT}/wave1_lane_m_plan_v2.json", timeout=1800)
if code != 0:
    raise SystemExit("plan v2 failed")
R.run(c, f"rm -f {OUT}/wave1_environment.json", timeout=30)
code, o, e = R.run(
    c, "cd /root/mk_v2 && PATH=/usr/local/cuda/bin:$PATH "
       f"{P} -u scripts/capture_fse_environment.py "
       f"--output {OUT}/wave1_environment.json", timeout=600)
R.run(c, f"{P} -c \"import json;"
         f"g=json.load(open('{OUT}/wave1_environment.json'));"
         "print('commit', g['git']['commit'][:12], 'dirty', g['git']['dirty'],"
         " 'nvcc', g['nvcc']['status'])\"", timeout=60)
c.close()
print("C3_WRAP_BUILD_DONE")
