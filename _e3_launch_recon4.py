"""Recon 4: strategy matrix content, mdir smoke wiring, B11 path."""
import _remote as R

c = R.connect()
print("#### configs/fse_strategy_matrix.json")
R.run(c, "cat /root/mk_v2/configs/fse_strategy_matrix.json", timeout=60)
print("#### e4_mdir_smoke wiring")
R.run(c, "ls /root/mk_v2_runs/e4_mdir_smoke/plans/ | head; "
         "head -c 800 /root/mk_v2_runs/e4_mdir_smoke/subjects.jsonl", timeout=60)
print("#### B11 mentions in scripts")
R.run(c, "grep -rln 'b11\\|compute-sanitizer\\|sanitizer' /root/mk_v2/scripts/ "
         "| head", timeout=60)
c.close()
print("RECON4_DONE")
