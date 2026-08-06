#!/usr/bin/env python3
"""Stage new code in /tmp/_mk_stage and run ALL gates (no production files
are touched): py_compile -> staged unit tests -> bit-exact comparison."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
_remote.run(c, "mkdir -p /tmp/_mk_stage", timeout=30, echo=False)
for local, remote in [
    ("_new_mutant_worker.py", "/tmp/_mk_stage/_mutant_worker.py"),
    ("_new_run_e1_cse_falsify.py", "/tmp/_mk_stage/run_e1_cse_falsify.py"),
    ("_new_test_gen_opt_bitexact.py", "/tmp/_mk_stage/test_gen_opt_bitexact.py"),
    ("_go_bitcompare_remote.py", "/tmp/_mk_stage/_go_bitcompare_remote.py"),
]:
    sftp.put(local, remote)
sftp.close()

GATES = [
    ("gate1 py_compile",
     "/root/miniconda3/bin/python -m py_compile /tmp/_mk_stage/_mutant_worker.py "
     "/tmp/_mk_stage/run_e1_cse_falsify.py /tmp/_mk_stage/test_gen_opt_bitexact.py "
     "&& echo PY_COMPILE_OK"),
    ("gate2 staged unit tests",
     "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= "
     "MK_WORKER_PATH=/tmp/_mk_stage/_mutant_worker.py "
     "/root/miniconda3/bin/python -m pytest /tmp/_mk_stage/test_gen_opt_bitexact.py -q 2>&1 | tail -5"),
    ("gate3 bit-exact comparison (several minutes)",
     "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= "
     "MK_STAGED_WORKER=/tmp/_mk_stage/_mutant_worker.py "
     "nice -n 15 /root/miniconda3/bin/python /tmp/_mk_stage/_go_bitcompare_remote.py"),
]
ok = True
for title, cmd in GATES:
    print("=" * 12, title)
    code, o, e = _remote.run(c, cmd, timeout=1500, echo=False)
    print(o.rstrip()[-2500:])
    if e.strip():
        print("STDERR:", e.strip()[-800:])
    if code != 0:
        print("GATE FAILED, exit", code)
        ok = False
        break
c.close()
print("GATES_ALL_GREEN" if ok else "GATES_FAILED")
