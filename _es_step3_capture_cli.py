"""Step 3: capture_fse_environment.py CLI + current git state."""
import _remote as R

c = R.connect()
R.run(c, "grep -n 'add_argument\\|def main' /root/mk_v2/scripts/capture_fse_environment.py | head",
      timeout=60)
R.run(c, "cd /root/mk_v2 && git log --oneline -3 && git status --porcelain | head",
      timeout=60)
c.close()
print("STEP3_DONE")
