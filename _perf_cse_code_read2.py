#!/usr/bin/env python3
"""Read-only: code bodies + kernel dims + live per-round wall sampling."""
import _remote

c = _remote.connect()
CMDS = [
    ("run_worker body", "sed -n '120,200p' /root/mk_v2/scripts/run_e1_probe_study.py"),
    ("executor 200-380", "sed -n '200,380p' /root/mk_v2/src/validation/executor.py"),
    ("policy_bank head", "sed -n '18,85p' /root/mk_v2/src/stress/policy_bank.py"),
    ("P53 dims", "grep -B2 -m1 'def Model\\|batch_size\\s*=\\|dim1\\s*=\\|dim2\\s*=' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '53_*.py' | head -1); grep -E '^(batch_size|dim1|dim2|dim|N|M|K|input_shape|features|scale)' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '53_*.py' | head -1)"),
    ("P96 dims", "grep -E '^(batch_size|dim1|dim2|dim|N|M|K|input_shape)' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '96_*.py' | head -1)"),
    ("P16 dims", "grep -E '^(batch_size|dim1|dim2|dim|N|M|K|input_shape)' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '16_*.py' | head -1)"),
    ("P20 dims", "grep -E '^(batch_size|dim1|dim2|dim|N|M|K|input_shape)' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '20_*.py' | head -1)"),
    ("P24 dims", "grep -E '^(batch_size|dim1|dim2|dim|N|M|K|input_shape)' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '24_*.py' | head -1)"),
    ("P27 dims", "grep -E '^(batch_size|dim1|dim2|dim|N|M|K|input_shape)' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '27_*.py' | head -1)"),
    ("P91 dims", "grep -E '^(batch_size|dim1|dim2|dim|N|M|K|input_shape)' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '91_*.py' | head -1)"),
    ("P1 dims", "grep -E '^(batch_size|dim1|dim2|dim|N|M|K|input_shape)' $(find /root/mk_v2 -path '*KernelBench*level1*' -name '1_*.py' | head -1)"),
    ("py-spy?", "which py-spy; /root/miniconda3/bin/py-spy --version 2>/dev/null; ls /root/miniconda3/bin/ | grep -i spy"),
    ("scratch res files", "ls -la --time-style=full-iso /root/mk_v2_runs/e1/e1cse_cazymsn_/ /root/mk_v2_runs/e1/e1cse_4kxu8tji/ 2>/dev/null"),
]
for title, cmd in CMDS:
    print("=" * 12, title)
    code, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    print(o.rstrip()[:6000])
    if e.strip():
        print("STDERR:", e.strip()[:300])
c.close()
print("DONE")
