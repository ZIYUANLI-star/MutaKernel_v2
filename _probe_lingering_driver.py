"""Why is a lane driver still alive after the queue drained?"""
import _remote

CMD = (
    "date '+NOW=%F %T'; echo SEP; "
    "pgrep -af '_b9_calib_driver_v2|run_e3_external|guard_b9_v2'; echo SEP; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo GPUEND; echo SEP; "
    "ls -la /root/mk_v2_runs/e3_b9_calib/B9_CALIB_V2_DONE_LANE0 /root/mk_v2_runs/e3_b9_calib/B9_CALIB_V2_DONE_LANE1 2>&1; echo SEP; "
    "tail -n 6 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo '---LANE1---'; "
    "tail -n 6 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log; echo SEP; "
    "tail -n 6 /root/mk_v2_runs/e3_b9_calib/guard_b9_v2.log; echo SEP; "
    "tail -n 4 /root/mk_v2_runs/e3_b9_calib/stage1_chain.log; echo SEP; "
    "for p in $(pgrep -f '_b9_calib_driver_v2'); do echo PID $p; cat /proc/$p/status | grep -E 'State|PPid'; cat /proc/$p/wchan 2>/dev/null; echo; py=1; done; echo SEP; "
    "tail -n 3 /root/mk_v2_runs/e3_b9_calib/wcfu_chain.log"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=120, echo=False)
c.close()
print(o)
print('LINGER_PROBE_DONE')
