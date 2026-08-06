import _remote
c = _remote.connect()
for path, local in [
    ("/root/mk_v2/src/stress/policy_bank.py", "_dl_policy_bank.py"),
]:
    code, out, err = _remote.run(c, "cat " + path, timeout=60, echo=False)
    with open(local, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", local, len(out), "bytes")
# grade_equiv_evidence source
print("=== grade_equiv_evidence source ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import inspect;from scripts.run_e1_probe_study import grade_equiv_evidence;print(inspect.getsource(grade_equiv_evidence))\"", timeout=60)
print("=== control3 log ===")
_remote.run(c, "cat /root/mk_v2_runs/e1/_p53_control3.log", timeout=30)
c.close()
