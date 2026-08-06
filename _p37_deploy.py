import _remote

c = _remote.connect()
# 1) backup the already-verified original, upload new version to a temp path
_remote.run(c, "cp /root/mk_v2/_final_window_go.py "
               "/root/mk_v2/_final_window_go.py.bak_pre_p37 && echo BACKUP_OK",
            timeout=30)
s = c.open_sftp()
s.put("_fw_go_source.py", "/root/mk_v2/_final_window_go.py.new")
s.close()
# 2) compile-check the new file BEFORE swapping, then atomic replace
for cmd in [
    "/root/miniconda3/bin/python -m py_compile /root/mk_v2/_final_window_go.py.new && echo NEW_PY_COMPILE_OK",
    "mv /root/mk_v2/_final_window_go.py.new /root/mk_v2/_final_window_go.py && "
    "/root/miniconda3/bin/python -m py_compile /root/mk_v2/_final_window_go.py && echo SWAP_AND_COMPILE_OK",
    "grep -c 'step3b_review_p37' /root/mk_v2/_final_window_go.py",
    # trigger still armed, marker not yet present, lane3 still running
    "pgrep -af 'final_window_trigger.sh' | grep -v 'bash -c'; "
    "ls /root/mk_v2_runs/e1/CSE_DONE_LANE3 2>/dev/null || echo LANE3_NOT_DONE_YET; "
    "ps -o pid,etime -p 200586",
]:
    print("### " + cmd[:70])
    _remote.run(c, cmd, timeout=60)
c.close()
print("P37_DEPLOY_DONE")
