"""Probe the V1 Sakana kernel loader (how CUDA_Code becomes a candidate)."""
import _remote as R

c = R.connect()
R.run(c, "grep -n 'load_inline\\|cpp_extension\\|module_fn\\|fn=' "
         "/root/mk_v2/scripts/run_fullscale_diff_test.py | head -25", timeout=60)
R.run(c, "grep -rn 'load_inline\\|cpp_extension' /root/mk_v2/src/ "
         "--include='*.py' | head -15", timeout=60)
R.run(c, "ls /root/mk_v2/external_benchmarks/ai_cuda_engineer/ 2>/dev/null | head",
      timeout=60)
c.close()
print("DONE")
