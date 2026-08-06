from math import comb

print("=== tiered rule: unescalated false-confirm = (1-p)^n_A * p  (j=1 only) ===")
best = max(((p / 1000.0) * (1 - p / 1000.0) ** 50, p / 1000.0) for p in range(1, 1000))
print("  n_A=50: worst %.5f at p=%.4f" % best)
for n in (20, 30, 50, 100):
    b = max(((p / 1000.0) * (1 - p / 1000.0) ** n, p / 1000.0) for p in range(1, 1000))
    print("  n_A=%-4d worst %.5f at p=%.4f ; at p=7.7%%: %.5f"
          % (n, b[0], b[1], 0.0769 * (1 - 0.0769) ** n))

print()
print("=== probability a GENUINE deterministic witness reproduces at j=1 ===")
print("  =1.0 by construction (identical input, deterministic mutant)")
print()
print("=== escalation band: P(2<=j<=20 | flake rate p) = (1-p)*(1-(1-p)^19) ===")
for p in (0.01, 0.02, 0.03, 0.077, 0.15):
    print("  p=%-6.3f %.4f" % (p, (1 - p) * (1 - (1 - p) ** 19)))
print()
print("=== escalation test: Fisher one-sided, control 0/200 vs candidate f/100 ===")


def fisher(n_ctrl, n_cand, f):
    return comb(n_cand, f) / comb(n_ctrl + n_cand, f)


for f in range(1, 7):
    print("  f=%d  p=%.5f" % (f, fisher(200, 100, f)))
print()
print("  with the production witness itself counted in the candidate arm (f+1):")
for f in range(0, 6):
    print("  observed f=%d -> f+1=%d  p=%.5f" % (f, f + 1, fisher(200, 101, f + 1)))
