#!/usr/bin/env python3
"""Verify local _dl copies match the deployed remote files before patching."""
import hashlib

import _remote


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


print("local _dl_mutant_worker.py      ", md5("_dl_mutant_worker.py"))
print("local _dl_run_e1_cse_falsify.py ", md5("_dl_run_e1_cse_falsify.py"))
c = _remote.connect()
_remote.run(c, "md5sum /root/mk_v2/scripts/_mutant_worker.py "
               "/root/mk_v2/scripts/run_e1_cse_falsify.py "
               "/root/mk_v2/tests/test_gen_opt_bitexact.py; "
               "ls /root/mk_v2/tests/ | grep -E 'cse|gen_opt'", timeout=60)
c.close()
