import _remote

CMD = (
    "sed -n '225,260p' /root/mk_v2/scripts/run_e1_cse_falsify.py; echo ---ARGS---; "
    "sed -n '290,345p' /root/mk_v2/scripts/run_e1_cse_falsify.py; echo ---CFG---; "
    "sed -n '410,470p' /root/mk_v2/scripts/run_e1_cse_falsify.py"
)
c = _remote.connect()
_remote.run(c, CMD, timeout=120)
c.close()
