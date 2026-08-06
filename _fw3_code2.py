import _remote

c = _remote.connect()
for cmd in [
    "sed -n '180,240p' /root/mk_v2/scripts/run_e1_cse_falsify.py",
    "sed -n '420,500p' /root/mk_v2/scripts/run_e1_cse_falsify.py",
    # worker invocation inside falsify driver
    "grep -n 'cfg\\|_mutant_worker\\|subprocess\\|Popen\\|json.dump' /root/mk_v2/scripts/run_e1_cse_falsify.py | sed -n '1,60p'",
    # equiv phase worker invocation
    "sed -n '620,700p' /root/mk_v2/scripts/run_e1_probe_study.py",
    "sed -n '700,790p' /root/mk_v2/scripts/run_e1_probe_study.py",
    # worker cfg keys
    "grep -n \"cfg\\.get\\|cfg\\[\" /root/mk_v2/scripts/_mutant_worker.py | head -50",
    # worker main / argv
    "grep -n 'def main\\|sys.argv\\|argparse' /root/mk_v2/scripts/_mutant_worker.py",
]:
    print("### " + cmd.split("\n")[0][:80])
    _remote.run(c, cmd, timeout=120)
c.close()
print("FW3_DONE")
