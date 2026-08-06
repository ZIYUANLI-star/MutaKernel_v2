"""Upload the E0 payload to the remote A800 and run the smoke test."""
import sys
import time

from _remote import connect, run

c = connect()

step = sys.argv[1] if len(sys.argv) > 1 else "setup"

if step == "setup":
    print("### uploading payload")
    sftp = c.open_sftp()
    sftp.put("_e0_payload.tar.gz", "/root/mk_v2_payload.tar.gz")
    sftp.close()
    run(c, "mkdir -p /root/mk_v2 && tar xzf /root/mk_v2_payload.tar.gz -C /root/mk_v2 && ls /root/mk_v2")
    run(c, "ls /usr/local/cuda/bin/nvcc 2>/dev/null; /usr/local/cuda/bin/nvcc --version 2>/dev/null | tail -1")
    run(c, "/root/miniconda3/bin/python -c \"import sys; sys.path.insert(0,'/root/mk_v2'); "
           "import src.validation, src.models; from src.mutengine import mutant_runner, mutant_runner_legacy; "
           "print('imports OK')\"")
    run(c, "/root/miniconda3/bin/python -c \"import torch; print(torch.__version__, torch.cuda.get_device_name(0))\"")
elif step == "patch":
    print("### uploading patch")
    sftp = c.open_sftp()
    sftp.put("_e0_patch.tar.gz", "/root/mk_v2_patch.tar.gz")
    sftp.close()
    run(c, "tar xzf /root/mk_v2_patch.tar.gz -C /root/mk_v2 && "
           "/root/miniconda3/bin/python -c \"import sys; sys.path.insert(0,'/root/mk_v2'); "
           "from src.mutengine import mutant_runner, mutant_runner_legacy; print('patch OK')\"")
elif step == "smoke":
    print("### smoke run (2 probes, both arms)")
    cmd = (
        "cd /root/mk_v2 && mkdir -p /root/mk_v2_runs && "
        "PATH=/usr/local/cuda/bin:$PATH TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
        "/root/miniconda3/bin/python -u scripts/run_e0_flip_rerun.py "
        "--details-dir phase1_details --kernelbench-root KernelBench "
        "--out-dir /root/mk_v2_runs/e0_smoke2 --mode smoke --limit 2 --timeout 300 2>&1 | tail -40"
    )
    run(c, cmd, timeout=1800)
    run(c, "cat /root/mk_v2_runs/e0_smoke2/observations.jsonl 2>/dev/null")
elif step == "launch":
    print("### launching sharded pilot in background (nohup x4)")
    per_cell = sys.argv[2] if len(sys.argv) > 2 else "30"
    shards = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    run(c, "pkill -f 'run_e0_flip_[r]erun' 2>/dev/null; "
           "pkill -f 'mk_v2/scripts/_mutant_[w]orker' 2>/dev/null; "
           "pkill -f '_mutant_worker_[l]egacy' 2>/dev/null; sleep 5; "
           "echo left_drivers=$(ps aux | grep 'run_e0_flip_[r]erun' | wc -l) "
           "left_workers=$(ps aux | grep '_mutant_[w]orker' | wc -l); "
           "nvidia-smi --query-gpu=memory.used --format=csv,noheader")
    mem_fraction = round(0.9 / shards, 2)
    run_tag = sys.argv[4] if len(sys.argv) > 4 else "run2"
    for i in range(shards):
        cmd = (
            "mkdir -p /root/mk_v2_runs && cd /root/mk_v2 && "
            "( nohup env PATH=/usr/local/cuda/bin:$PATH "
            "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext "
            f"MK_GPU_MEMORY_FRACTION={mem_fraction} "
            "/root/miniconda3/bin/python -u scripts/run_e0_flip_rerun.py "
            "--details-dir phase1_details --kernelbench-root KernelBench "
            f"--out-dir /root/mk_v2_runs/e0_{run_tag}_s{i} --mode pilot "
            f"--per-cell {per_cell} --timeout 420 "
            f"--shard-index {i} --shard-count {shards} "
            f"> /root/mk_v2_runs/e0_{run_tag}_s{i}.log 2>&1 < /dev/null & ) ; "
            f"echo LAUNCHED_S{i}"
        )
        run(c, cmd, timeout=60)
elif step == "status":
    tag = sys.argv[2] if len(sys.argv) > 2 else "run2"
    run(c, f"for i in 0 1 2 3; do if [ -f /root/mk_v2_runs/e0_{tag}_s$i.log ]; then "
           f"echo \"--- shard $i:\"; tail -2 /root/mk_v2_runs/e0_{tag}_s$i.log; "
           f"wc -l /root/mk_v2_runs/e0_{tag}_s$i/observations.jsonl 2>/dev/null; fi; done; "
           "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
           "echo procs=$(ps aux | grep 'run_e0_flip_[r]erun' | wc -l)")
elif step == "collect":
    print("### collecting results")
    run(c, "cd /root/mk_v2_runs && tar czf e0_results.tar.gz e0_*_s*/ e0_smoke2/ e0_*_s*.log 2>/dev/null; ls -la e0_results.tar.gz")
    sftp = c.open_sftp()
    sftp.get("/root/mk_v2_runs/e0_results.tar.gz", "_e0_results.tar.gz")
    sftp.close()
    print("downloaded _e0_results.tar.gz")

c.close()
print("STEP_DONE:" + step)
