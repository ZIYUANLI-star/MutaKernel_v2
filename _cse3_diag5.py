#!/usr/bin/env python3
import _remote

c = _remote.connect()
for n in (22, 23, 46, 49, 52, 53):
    _remote.run(c, f"f=$(ls /root/mk_v2/KernelBench/KernelBench/level1/{n}_*.py);"
                   " echo \"== $f ==\";"
                   " grep -E '^(batch_size|dim|dim1|dim2|channels|depth|height|"
                   "width|features|kernel_size|stride|padding)\\s*=' $f",
                timeout=60)
c.close()
