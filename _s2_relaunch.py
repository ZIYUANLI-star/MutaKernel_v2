"""Requeue the L1_P45 pair, then reliably relaunch the guard at 105GiB."""
import time
import _remote

c = _remote.connect()

# 1. requeue L1_P45 pair (stage-1 tail units, also SIGKILLed today)
_, o, e = _remote.run(c, (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, shutil\n"
    "from datetime import datetime\n"
    "from pathlib import Path\n"
    "OUT=Path('/root/mk_v2_runs/e3_b9_calib'); QS=OUT/'queue_state.json'\n"
    "TS=datetime.now().strftime('%Y%m%dT%H%M%S')\n"
    "q=json.loads(QS.read_text())\n"
    "shutil.copy2(QS, OUT/('queue_state.json.bak_p45_'+TS))\n"
    "moved=[]\n"
    "for u in ('L1_P45__float32','L1_P45__float16'):\n"
    "    d=q['done']\n"
    "    if isinstance(d,dict): present=u in d\n"
    "    else: present=u in d\n"
    "    if present:\n"
    "        (d.pop(u,None) if isinstance(d,dict) else d.remove(u))\n"
    "        if u not in q['pending']: q['pending'].append(u); moved.append(u)\n"
    "tmp=QS.with_suffix('.tmp'); tmp.write_text(json.dumps(q,indent=1)); tmp.replace(QS)\n"
    "print('P45 requeued:', moved, 'pending:', len(q['pending']))\n"
    "EOF"), timeout=60, echo=False)
print(o)
if e.strip():
    print("STDERR:", e[-1000:])

# 2. relaunch guard via a launcher file (avoids inline & race)
_, o, _ = _remote.run(c, (
    "cat > /root/mk_v2_runs/e3_b9_calib/launch_guard_105.sh <<'EOF'\n"
    "#!/bin/bash\n"
    "cd /root/mk_v2_runs/e3_b9_calib\n"
    "export LANES=2 BUDGET_GB=105\n"
    "setsid bash guard_b9_v2.sh >> guard_b9_v2_stage2.out 2>&1 < /dev/null &\n"
    "echo launched $!\n"
    "EOF\n"
    "chmod +x /root/mk_v2_runs/e3_b9_calib/launch_guard_105.sh && "
    "bash /root/mk_v2_runs/e3_b9_calib/launch_guard_105.sh"),
    timeout=30, echo=False)
print(o)

time.sleep(70)
_, o, _ = _remote.run(c, (
    "pgrep -af '[g]uard_b9_v2.sh|[_]b9_calib_driver_v2' | head -5; echo ---; "
    "tail -4 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log; echo ---; "
    "tail -2 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo ---; "
    "tail -2 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log; echo ---; "
    "nvidia-smi --query-gpu=memory.used --format=csv,noheader"),
    timeout=60, echo=False)
print(o)
c.close()
print("RELAUNCH_DONE")
