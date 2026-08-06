import os
import _remote as R

c = R.connect()
sftp = c.open_sftp()
for remote, local in [
    ("/root/mk_v2/src/experiments/external_ports/b7_robust_kbench.py",
     "_remote_src/b7_robust_kbench.py"),
    ("/root/mk_v2/src/experiments/external_ports/b8_kernelbenchx.py",
     "_remote_src/b8_kernelbenchx.py"),
]:
    sftp.get(remote, local)
    print("fetched", local, os.path.getsize(local))
try:
    sftp.get("/root/mk_v2/configs/external_baselines.json",
             "_remote_src/external_baselines.json")
    print("fetched external_baselines.json")
except FileNotFoundError:
    print("no configs/external_baselines.json")
sftp.close()
R.run(c, "ls /root/robust_kbench_data/highlighted/layernorm/forward/; "
         "head -50 /root/robust_kbench_data/problems/problem_layernorm.py; "
         "ls /root/KernelBenchX_hf/kernelbenchx/Activation | head -5; "
         "head -60 /root/KernelBenchX_hf/kernelbenchx/Activation/gelu_bf16.py",
      timeout=60)
c.close()
print("DONE")
