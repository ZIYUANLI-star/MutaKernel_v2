"""Worker candidate-class conventions."""
import _remote as R

c = R.connect()
R.run(c, "grep -n 'ModelNew' /root/mk_v2/scripts/_candidate_worker.py | head",
      timeout=60)
R.run(c, "grep -n 'candidate_classes' /root/mk_v2/scripts/_candidate_worker.py "
         "| head", timeout=60)
R.run(c, "grep -n 'def .*candidate\\|import_module\\|spec_from_file' "
         "/root/mk_v2/scripts/_candidate_worker.py | head -15", timeout=60)
c.close()
print("DONE")
