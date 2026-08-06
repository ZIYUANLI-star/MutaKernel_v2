import _remote

CMD = (
    "cd /root/mk_v2 && "
    "grep -n 'add_argument' scripts/run_e1_cse_falsify.py | head -40; "
    "echo ---FINALGO---; "
    "grep -n 'final_requeue' scripts/_final_window_go.py | head; "
    "echo ---CMDSHAPE---; "
    "grep -n 'run_e1_cse_falsify' scripts/_final_window_go.py | head; "
    "echo ---SKIP---; "
    "cat /root/mk_v2_runs/e1/cse_policy_skip.json"
)
c = _remote.connect()
_remote.run(c, CMD, timeout=120)
c.close()
