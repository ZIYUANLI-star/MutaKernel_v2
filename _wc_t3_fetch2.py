import _remote, os, json

c = _remote.connect()
E1 = "/root/mk_v2_runs/e1"
R = E1 + "/witness_confirmation"
cmds = [
    f"ls {R}/cells/*.json | wc -l; ls {R}/cells/*.workerlog 2>/dev/null | wc -l",
    f"ls -la {E1}/_wc_witness_inventory.json {E1}/_wc_round_counts.json {E1}/_wc_round_wall.json {E1}/_wc_seed_shortcut.json 2>&1",
    "grep -c oom_kill /dev/null; cat /sys/fs/cgroup/memory.events 2>/dev/null || cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null",
    f"ls {R}/STAGE_DONE_* 2>/dev/null; echo '--'; ls {R}/STARTER_DONE 2>/dev/null; echo '--'",
    "ls -la /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN 2>&1; ls /root/mk_v2_runs/e3_b9_calib/*brake* 2>/dev/null; ls /root/mk_v2_runs/e3_b9_calib/ | head -40",
    "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv",
    "free -g | sed -n 2p",
]
for cmd in cmds:
    print("### " + cmd)
    _remote.run(c, cmd, timeout=120)

sftp = c.open_sftp()
os.makedirs("_wc_local", exist_ok=True)
for src, dst in [
    (R + "/plan.json", "_wc_local/plan.json"),
    (E1 + "/_wc_witness_inventory.json", "_wc_local/_wc_witness_inventory.json"),
    (R + "/wc1_report.json", "_wc_local/wc1_report.json"),
]:
    try:
        sftp.get(src, dst); print("got", src)
    except Exception as e:
        print("skip", src, e)
for extra in ["_wc_round_counts.json", "_wc_round_wall.json", "_wc_seed_shortcut.json"]:
    try:
        sftp.get(E1 + "/" + extra, "_wc_local/" + extra); print("got", extra)
    except Exception as e:
        print("skip", extra, e)
sftp.close()
c.close()
print("DONE_FETCH2")
