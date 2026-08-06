import _remote, os
c = _remote.connect()
s = c.open_sftp()
os.makedirs("_wc_ref", exist_ok=True)
for src, dst in [
    ("/root/mk_v2/scripts/_mutant_worker.py", "_wc_ref/mutant_worker.py"),
    ("/root/mk_v2/_p37_newwitness_review.py", "_wc_ref/p37_newwitness_review.py"),
    ("/root/mk_v2/scripts/policy_bank.py", "_wc_ref/policy_bank.py"),
]:
    try:
        s.get(src, dst)
        print("got", src, os.path.getsize(dst))
    except Exception as e:
        print("FAIL", src, e)
s.close()
_remote.run(c, "ls /root/mk_v2/scripts/ | grep -i -E 'policy|harness|oracle|runner' ")
c.close()
