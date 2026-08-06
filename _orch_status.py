import _remote

c = _remote.connect()
_remote.run(c, (
    "ps aux | grep '_signoff_[o]rch' | awk '{print $2, $9}'; echo ---LOG---; "
    "tail -15 /root/mk_v2_runs/signoff_orch.log 2>/dev/null; echo ---STDOUT---; "
    "tail -5 /root/mk_v2_runs/signoff_orch_stdout.log 2>/dev/null; echo ---CSE---; "
    "ps aux | grep -E 'run_e1_cse_[f]alsify|_mutant_[w]orker' | awk '{print $2, $12, $13}'"
), timeout=90)
c.close()
