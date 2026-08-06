"""Check remote materialized corpora + C5 sample tree availability."""
import _remote

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "echo ===EXT_BENCH===; ls /root/mk_v2/external_benchmarks/ 2>/dev/null; "
    "for d in /root/mk_v2/external_benchmarks/*/; do echo $d; ls $d | head -3; "
    "ls $d/problems 2>/dev/null | head -3; done 2>/dev/null; "
    "echo ===REGISTRY===; ls /root/mk_v2/external_benchmarks/*/*.json 2>/dev/null | head -6; "
    "echo ===C5_RAW===; ls /root/mk_v2/external/ 2>/dev/null; "
    "find /root/mk_v2 -maxdepth 3 -iname '*kernelbench_sample*' 2>/dev/null | head -5; "
    "find /root/mk_v2 -maxdepth 2 -iname '*sample*' -type d 2>/dev/null | head -8"),
    timeout=90, echo=False)
print(o)
c.close()
