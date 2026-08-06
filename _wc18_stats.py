"""Power / false-confirmation numbers for the WC-1 pre-registration."""
from math import comb

p37 = 3 / 39.0
print("observed L1_P37 sparse_extreme flake rate: 3/39 = %.4f" % p37)
print()
print("=== criterion (a): P(all n control rounds pass | flake rate p) ===")
for n in (3, 9, 10, 20, 30, 50, 100):
    print("  n=%-4d p=7.7%%: %.4f   p=5%%: %.4f   p=3%%: %.4f   p=1%%: %.4f"
          % (n, (1 - p37) ** n, 0.95 ** n, 0.97 ** n, 0.99 ** n))
print()
print("  the 2026-07-30 P37 review used 3 reps x 3 rounds = 9 control rounds")
print("  -> miss probability at p=7.7%% was %.3f (it fired anyway)" % ((1 - p37) ** 9))
print("  3 reps read as 3 rounds -> %.4f" % ((1 - p37) ** 3))
print()


def joint(n_a, n_b, k, p):
    """P(spurious witness survives WC-1) = P(control clean) * P(>=k of n_b)."""
    ctrl = (1 - p) ** n_a
    rep = sum(comb(n_b, i) * p ** i * (1 - p) ** (n_b - i) for i in range(k, n_b + 1))
    return ctrl * rep


print("=== joint false-confirmation rate, worst case over p ===")
grid = [i / 1000.0 for i in range(1, 501)]
for n_a, n_b, k in [(20, 5, 1), (20, 20, 1), (30, 20, 1), (50, 5, 1),
                    (50, 20, 1), (50, 20, 2), (100, 20, 1)]:
    vals = [(joint(n_a, n_b, k, p), p) for p in grid]
    m, argm = max(vals)
    print("  n_A=%-4d n_B=%-3d k=%d : worst %.4f at p=%.3f | at p=7.7%%: %.4f"
          % (n_a, n_b, k, m, argm, joint(n_a, n_b, k, p37)))
print()
print("=== criterion (b) false-negative risk for a GENUINE intermittent mutant ===")
print("  (mutation itself introduces a race reproducing at rate q)")
for q in (0.01, 0.03, 0.077, 0.15, 0.3, 0.5):
    print("  q=%-6.3f P(0 of 20 reproduce)=%.4f   P(<2 of 20)=%.4f   P(<2 of 5)=%.4f"
          % (q, (1 - q) ** 20,
             (1 - q) ** 20 + 20 * q * (1 - q) ** 19,
             (1 - q) ** 5 + 5 * q * (1 - q) ** 4))
