#!/usr/bin/env python3
"""Pull get_inputs sources for the kernels involved in the memory account."""
import _remote

c = _remote.connect()
for n in (22, 23, 46, 49, 52, 53):
    _remote.run(c, f"f=$(ls /root/mk_v2/KernelBench/KernelBench/level1/{n}_*.py);"
                   f" echo \"== $f ==\"; sed -n '1,15p' $f;"
                   " awk '/def get_inputs|def get_init_inputs/,/return/' $f",
                timeout=60)
c.close()
