"""Brake API + stage1_chain tail behavior."""
import _remote

CMD1 = (
    "grep -n 'def \\|argparse\\|add_argument\\|OWNER\\|hold\\|release\\|sync' /root/mk_v2/_b9_brake.py | head -40; echo SEP; "
    "sed -n '1,40p' /root/mk_v2/_b9_brake.py"
)
CMD2 = "sed -n '396,435p' /root/mk_v2/_b9_stage1_chain.py; echo SEP; sed -n '505,540p' /root/mk_v2/_b9_stage1_chain.py"

c = _remote.connect()
print('##### brake api #####')
_, o, _ = _remote.run(c, CMD1, timeout=60, echo=False)
print(o)
print('##### chain tail #####')
_, o, _ = _remote.run(c, CMD2, timeout=60, echo=False)
c.close()
print(o)
print('ADV_INSPECT6_DONE')
