"""Read code sections needed for the patch and followup tooling."""
import _remote

CMD1 = "sed -n '235,300p' /root/mk_v2/scripts/run_e3_external.py"
CMD2 = (
    "sed -n '1,60p' /root/mk_v2/_wc_audit.py; echo SEP_USAGE; "
    "grep -n 'argparse\\|add_argument\\|def main' /root/mk_v2/_wc_audit.py | head -20"
)
CMD3 = (
    "grep -n 'def \\|cell_id\\|top_up\\|topup' /root/mk_v2/_wc_analyze.py | head -30; echo SEP; "
    "sed -n '1,50p' /root/mk_v2/_e1_requeue_remote.py 2>/dev/null | head -50; echo SEP; "
    "ls /root/mk_v2_runs/e1/ | head -30"
)

c = _remote.connect()
print('##### run_e3_external 235-300 #####')
_, o, _ = _remote.run(c, CMD1, timeout=60, echo=False)
print(o)
print('##### _wc_audit head #####')
_, o, _ = _remote.run(c, CMD2, timeout=60, echo=False)
print(o)
print('##### analyze/requeue/runs #####')
_, o, _ = _remote.run(c, CMD3, timeout=60, echo=False)
c.close()
print(o)
print('ADV_INSPECT3_DONE')
