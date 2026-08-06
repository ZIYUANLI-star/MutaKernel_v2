"""Inspect the L1_P22 run_error details."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "echo ===TASK===; /root/miniconda3/bin/python -c \"import json; "
    "q=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); "
    "u=q['units']['L1_P22__float32']; "
    "print(u['task_file'], u['out_numel'], u['in_numel'], u['est_peak_gb'])\"; "
    "echo ===F32_DIR===; ls -la /root/mk_v2_runs/e3_b9_calib/units/L1_P22__float32/; "
    "echo ===F32_LOG===; tail -c 3000 /root/mk_v2_runs/e3_b9_calib/units/L1_P22__float32/run.log; "
    "echo; echo ===F16_LOG===; tail -c 2000 /root/mk_v2_runs/e3_b9_calib/units/L1_P22__float16/run.log; "
    "echo; echo ===CALIB_ROW===; "
    "grep -h 'L1_P22' /root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl | tail -4"),
    timeout=90, echo=False)
print(o)
c.close()
