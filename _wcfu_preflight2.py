"""Preflight 2: driver row output + plan regeneration behavior."""
import _remote

CMD1 = "sed -n '200,260p' /root/mk_v2/_b9_calib_driver_v2.py"
CMD2 = (
    "grep -n 'jsonl\\|rows\\|append\\|open(' /root/mk_v2/_b9_calib_driver_v2.py | head -25; echo SEP; "
    "ls /root/mk_v2_runs/e3_b9_calib/*.jsonl 2>/dev/null; "
    "ls /root/mk_v2_runs/e3_b9_calib/ | grep -vE 'units|brakes' | head -40"
)

c = _remote.connect()
print('##### driver 200-260 #####')
_, o, _ = _remote.run(c, CMD1, timeout=60, echo=False)
print(o)
print('##### rows location #####')
_, o, _ = _remote.run(c, CMD2, timeout=60, echo=False)
c.close()
print(o)
print('PREFLIGHT2_DONE')
