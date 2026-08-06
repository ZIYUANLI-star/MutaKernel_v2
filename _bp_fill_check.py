"""Verify fillability of the 5.5 escape-mechanism sentence + CSE bitwise count.

1. escape_mechanisms.json: built at map freeze (post-amendment). Check its
   basis (68 witnessed) + the five-mechanism distribution.
2. CSE final artifacts: count of tolerance-conforming bitwise divergences
   (excluded from the 7 falsifications).
"""
import _remote as R

py = r"""
import json
d = json.load(open('/root/mk_v2_runs/e1/escape_mechanisms.json'))
print(json.dumps(d, indent=1)[:2200])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_bp_fc.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _bp_fc.py",
      timeout=120)
print("### CSE artifacts")
R.run(c, "ls /root/mk_v2_runs/e1/ | grep -i cse | head; "
         "ls /root/mk_v2_runs/e1_cse* 2>/dev/null | head", timeout=60)
c.close()
print("FILL_CHECK_DONE")
