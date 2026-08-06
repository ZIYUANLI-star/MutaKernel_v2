import _remote, sys
c = _remote.connect()
R = _remote.run
R(c, "tail -25 /root/mk_v2_runs/e1/witness_confirmation/audit.log; echo '--- cells done:'; ls /root/mk_v2_runs/e1/witness_confirmation/cells/*.json 2>/dev/null | wc -l; nvidia-smi --query-gpu=memory.used --format=csv,noheader; free -g | sed -n 2p; date")
c.close()
