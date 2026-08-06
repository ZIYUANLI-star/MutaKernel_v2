"""Build the witness inventory: CSE FALSIFIED + equiv WITNESSED, per kernel."""
import _remote
c = _remote.connect()
R = _remote.run

print("=== e1 dir listing (rest) ===")
R(c, "ls -la /root/mk_v2_runs/e1/ | tail -50")
print("=== analysis dir ===")
R(c, "find /root/mk_v2_runs/e1/analysis -maxdepth 2 -type f | head -60")
print("=== final_window_review dir ===")
R(c, "ls -la /root/mk_v2_runs/e1/final_window_review/")
print("=== scripts of interest ===")
R(c, "ls -la /root/mk_v2/scripts/ | head -60; echo ---; ls /root/mk_v2/*.py | head -80")
c.close()
print("DONE")
