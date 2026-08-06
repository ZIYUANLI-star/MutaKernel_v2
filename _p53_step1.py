import _remote
c = _remote.connect()
_remote.run(c, "ls -la /root/mk_v2/scripts/ | grep -Ei 'cse|worker|falsif|grade'", timeout=30)
print("=== wc ===")
_remote.run(c, "wc -l /root/mk_v2/scripts/run_e1_cse_falsify.py /root/mk_v2/scripts/_mutant_worker.py", timeout=30)
print("=== lane3 log tail ===")
_remote.run(c, "tail -n 40 /root/mk_v2_runs/e1_cse_lane3.log", timeout=30)
c.close()
