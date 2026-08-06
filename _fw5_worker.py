import _remote

c = _remote.connect()
for cmd in [
    "sed -n '120,175p' /root/mk_v2/scripts/run_e1_probe_study.py",
    "sed -n '348,376p' /root/mk_v2/scripts/run_e1_probe_study.py",
    # worker result assembly (equiv mode): find where result dict is built
    "grep -n 'valid_rounds\\|\"trials\"\\|divergence\\|tested_policies\\|status.*pass\\|result = ' /root/mk_v2/scripts/_mutant_worker.py | sed -n '1,40p'",
    "sed -n '380,420p' /root/mk_v2/scripts/_mutant_worker.py",
    "sed -n '820,880p' /root/mk_v2/scripts/_mutant_worker.py",
]:
    print("### " + cmd.split("\n")[0][:90])
    _remote.run(c, cmd, timeout=120)
c.close()
print("FW5_DONE")
