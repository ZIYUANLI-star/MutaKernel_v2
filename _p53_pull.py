import _remote
c = _remote.connect()
for path, local in [
    ("/root/mk_v2/scripts/run_e1_cse_falsify.py", "_dl_run_e1_cse_falsify.py"),
    ("/root/mk_v2/scripts/_mutant_worker.py", "_dl_mutant_worker.py"),
]:
    code, out, err = _remote.run(c, "cat " + path, timeout=60, echo=False)
    with open(local, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", local, len(out), "bytes, exit", code)
c.close()
