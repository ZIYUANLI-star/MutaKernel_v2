"""Read-only probe of the remote server's existing MutaKernel state."""
from _remote import connect, run

c = connect()
for cmd in [
    "ps aux --sort=-%cpu | head -15",
    "cd /root/MutaKernel && git log --oneline -5 2>/dev/null; git branch --show-current 2>/dev/null; git status --short 2>/dev/null | head -5",
    "ls /root/MutaKernel | head -40",
    "ls /root/MutaKernel/fse_runs 2>/dev/null | head -20",
    "ls /root/autodl-tmp 2>/dev/null | head -30",
    "tail -5 /root/matrix_nohup.log 2>/dev/null",
    "tail -5 /root/run_rq4_pipeline.nohup.log 2>/dev/null",
    "tail -5 /root/_full_supervisor.out 2>/dev/null",
    "tail -5 /root/_gpuemu_sup.out 2>/dev/null",
    "ls /root/miniconda3/envs 2>/dev/null",
    "/root/miniconda3/bin/python --version 2>/dev/null; /root/miniconda3/bin/python -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())' 2>&1 | tail -1",
    "crontab -l 2>/dev/null | head -5",
]:
    print("### " + cmd)
    run(c, cmd, timeout=120)
c.close()
print("PROBE_DONE")
