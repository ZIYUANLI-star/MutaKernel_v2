import _remote

c = _remote.connect()
for name, cmd in [
    ("worker_abort_paths", "grep -n 'watchdog\\|abort\\|deadline\\|partial\\|break\\|give.up\\|bail' /root/mk_v2/scripts/_mutant_worker.py | head -30"),
    ("p52_input_size", "grep -rn 'randn\\|rand(' /root/mk_v2/KernelBench/level1/52_*.py 2>/dev/null | head -5; ls /root/mk_v2/KernelBench/level1/ | grep '^52'"),
]:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o.rstrip()[:4000])
    if e.strip():
        print("STDERR:", e[:500])
c.close()
