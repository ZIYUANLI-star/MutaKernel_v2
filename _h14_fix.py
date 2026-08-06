"""Read the deployed torch.quantile fix + error_stats memory rewrite."""
import _remote

c = _remote.connect()
for cmd in [
    "grep -n 'QUANTILE_NUMEL_LIMIT\\|_exact_percentiles\\|def error_stats\\|def calibrate_tolerance\\|mean_abs\\|def compare_to_fp64' "
    "/root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py",
    "sed -n '/^QUANTILE_NUMEL_LIMIT/,/^def compare_to_fp64/p' /root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py",
    "grep -n 'def calibrate_tolerance' -A 30 /root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py",
    "diff /root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py "
    "/root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py.bak_quantile_fix",
    "echo '== oom counter source =='; sed -n '50,70p' /root/mk_v2/_signoff_orch.py",
]:
    print("\n#### " + cmd[:78])
    _remote.run(c, cmd, timeout=180)
c.close()
print("\nH14_DONE")
