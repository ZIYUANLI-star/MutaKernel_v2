"""Start a 35-minute GPU memory sampler on the remote (10s cadence)."""
import _remote

c = _remote.connect()
try:
    _remote.run(
        c,
        "rm -f /root/mk_v2_runs/e1_mem_samples.log; "
        "nohup bash -c 'for i in $(seq 210); do "
        "nvidia-smi --query-gpu=memory.used --format=csv,noheader >> /root/mk_v2_runs/e1_mem_samples.log; "
        "sleep 10; done' > /dev/null 2>&1 & echo SAMPLER_STARTED",
        timeout=20,
    )
except Exception as exc:
    print("sampler launch (tolerated):", type(exc).__name__, exc)
c.close()
print("MEMSAMPLE_DONE")
