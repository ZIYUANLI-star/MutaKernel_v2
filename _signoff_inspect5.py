import _remote

CMD = (
    "ls /root/mk_v2/_final_window* /root/mk_v2/*final* 2>/dev/null; "
    "echo ---; "
    "grep -n 'run_e1_cse_falsify\\|only\\|ROUND_TIMEOUT\\|round_timeout\\|requeue' "
    "/root/mk_v2/_final_window_go.py 2>/dev/null | head -60; "
    "echo ---DRIVERSEL---; "
    "grep -n 'only\\|targets\\|completed' /root/mk_v2/scripts/run_e1_cse_falsify.py | head -40; "
    "echo ---RT---; "
    "grep -n 'MK_\\|ROUND_TIMEOUT' /root/mk_v2/scripts/run_e1_cse_falsify.py | head -20"
)
c = _remote.connect()
_remote.run(c, CMD, timeout=120)
c.close()
