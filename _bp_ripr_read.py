"""Read classify_escape from src/audit/ripr.py."""
import _remote as R

c = R.connect()
R.run(c, "grep -n -A 45 'def classify_escape' /root/mk_v2/src/audit/ripr.py",
      timeout=60)
c.close()
print("DONE")
