import _remote

c = _remote.connect()
for cmd in [
    # driver: argparse detail + file naming + lane/completed logic
    "sed -n '280,420p' /root/mk_v2/scripts/run_e1_cse_falsify.py",
    "grep -n 'lane_tag\\|completed\\|observations' /root/mk_v2/scripts/run_e1_cse_falsify.py | head -60",
    # probe study: full argparse + equiv file naming
    "sed -n '880,960p' /root/mk_v2/scripts/run_e1_probe_study.py",
    "grep -n 'lane_tag\\|completed\\|observations\\|def main' /root/mk_v2/scripts/run_e1_probe_study.py | head -60",
    # round watchdog 90s: where defined, is it configurable
    "grep -n 'ROUND_TIMEOUT\\|round_timeout\\|watchdog\\|alarm\\|90' /root/mk_v2/scripts/_mutant_worker.py | head -40",
    # sentinel: which files/lanes it watches, will it touch a tagged driver
    "grep -n 'LANE\\|lane\\|DONE\\|pgrep\\|kill' /root/mk_v2/e1_sentinel.py | head -80",
]:
    print("### " + cmd.split("\n")[0][:80])
    _remote.run(c, cmd, timeout=120)
c.close()
print("FW2_DONE")
