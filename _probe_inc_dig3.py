import _remote

c = _remote.connect()
for name, cmd in [
    ("find_cse_log", "ls -la /root/mk_v2_runs/e1/worker_logs/ | grep -i 'P52.*arith.*11'"),
    ("cse_log_stdout", "sed -n '1,60p' /root/mk_v2_runs/e1/worker_logs/L1_P52__arith_replace__11_cse.log 2>/dev/null"),
    ("cse_log_tail", "tail -60 /root/mk_v2_runs/e1/worker_logs/L1_P52__arith_replace__11_cse.log 2>/dev/null"),
    ("driver_code_430_500", "sed -n '430,505p' /root/mk_v2/scripts/run_e1_cse_falsify.py"),
]:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o.rstrip()[:6000])
    if e.strip():
        print("STDERR:", e[:500])
c.close()
