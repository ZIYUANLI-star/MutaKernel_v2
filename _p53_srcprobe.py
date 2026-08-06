import _remote
c = _remote.connect()
print("=== mixed_extremes builder + _apply_to_tensor + fn (full context) ===")
_remote.run(c, "cd /root/mk_v2 && grep -n 'mixed_extremes\\|_apply_to_tensor\\|def _register\\|def policy' src/stress/policy_bank.py | head -40", timeout=30)
print("=== _apply_to_tensor source ===")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -c \"import inspect;from src.stress import policy_bank as pb;print(inspect.getsource(pb._apply_to_tensor))\"", timeout=60)
print("=== host mem + swap now ===")
_remote.run(c, "free -g; echo ---; cat /sys/fs/cgroup/memory.max 2>/dev/null || cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null", timeout=30)
c.close()
