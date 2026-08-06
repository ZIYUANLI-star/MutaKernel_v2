import _remote

c = _remote.connect()
_remote.run(c, (
    "grep -n 'MK_CSE_ROUND_TIMEOUT' /root/mk_v2/scripts/run_e1_cse_falsify.py; "
    "echo ---IMPORTS---; "
    "grep -n '^import\\|^from' /root/mk_v2/scripts/run_e1_cse_falsify.py | head -20; "
    "echo ---BAK---; ls -la /root/mk_v2/scripts/run_e1_cse_falsify.py*"
), timeout=60)
c.close()
