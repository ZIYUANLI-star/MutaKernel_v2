"""Session helper for the remote GPU server (password from REMOTE_PW env).

Windows-side paramiko client. Delete after the experiment campaign.
"""
import os
import sys
import time

import paramiko

HOST, PORT, USER = "connect.nma1.seetacloud.com", 22841, "root"


def connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER,
                   password=os.environ["REMOTE_PW"], timeout=45,
                   banner_timeout=45, auth_timeout=45)
    return client


def run(client, cmd, timeout=600, echo=True):
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode(errors="replace")
    e = err.read().decode(errors="replace")
    code = out.channel.recv_exit_status()
    if echo:
        if o.strip():
            print(o.rstrip())
        if e.strip():
            print("STDERR:", e.rstrip()[:2000])
        if code != 0:
            print("EXIT:", code)
    return code, o, e


if __name__ == "__main__":
    c = connect()
    for cmd in [
        "hostname; uptime",
        "nvidia-smi --query-gpu=index,name,memory.total,memory.used,driver_version --format=csv",
        "python3 --version; which python3 pip3",
        "python3 -c 'import torch; print(\"torch\", torch.__version__, \"cuda\", torch.version.cuda, torch.cuda.is_available(), torch.cuda.device_count())' 2>&1 | tail -1",
        "python3 -c 'import triton; print(\"triton\", triton.__version__)' 2>&1 | tail -1",
        "nvcc --version 2>/dev/null | tail -1; gcc --version | head -1",
        "df -h /root | tail -1; free -g | sed -n 2p; nproc",
        "ls /root",
    ]:
        print("### " + cmd)
        run(c, cmd, timeout=120)
    c.close()
    print("RECON_DONE")
