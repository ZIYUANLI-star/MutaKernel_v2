"""Final groundwork: audit rerun semantics, stage1 chain completion, _instantiate."""
import _remote

CMD1 = (
    "grep -n '_instantiate\\|def _run_b9\\|def _mode_b9\\|b9' /root/mk_v2/scripts/run_e3_external.py | head -25; echo SEP; "
    "sed -n '300,375p' /root/mk_v2/scripts/run_e3_external.py"
)
CMD2 = (
    "grep -n 'def cmd_run\\|def run_cell\\|json.dump\\|exists\\|skip\\|force\\|b9\\|brake' /root/mk_v2/_wc_audit.py | head -40"
)
CMD3 = (
    "sed -n '1,80p' /root/mk_v2/_b9_stage1_chain.py"
)

c = _remote.connect()
print('##### e3 b9 mode + instantiate #####')
_, o, _ = _remote.run(c, CMD1, timeout=60, echo=False)
print(o)
print('##### wc_audit run semantics #####')
_, o, _ = _remote.run(c, CMD2, timeout=60, echo=False)
print(o)
print('##### stage1 chain #####')
_, o, _ = _remote.run(c, CMD3, timeout=60, echo=False)
c.close()
print(o)
print('ADV_INSPECT4_DONE')
