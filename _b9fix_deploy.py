# -*- coding: utf-8 -*-
"""Back up + deploy the B9 error_stats fix and run the CPU-only test suite.

No GPU is touched: CUDA_VISIBLE_DEVICES is emptied for every command.
"""
import hashlib

import _remote as R

REMOTE_SRC = "/root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py"
REMOTE_TEST = "/root/mk_v2/tests/test_b9_error_stats_bitexact.py"
PY = "/root/miniconda3/bin/python"


def put(sftp, local, remote):
    with open(local, "rb") as fh:
        body = fh.read().replace(b"\r\n", b"\n")
    with sftp.open(remote, "wb") as fh:
        fh.write(body)
    return hashlib.md5(body).hexdigest()


c = R.connect()

print("### backup (once, never overwritten)")
R.run(c, "cd /root/mk_v2/src/experiments/external_ports && "
         "if [ ! -f b9_seeded_fuzzing.py.bak_quantile_fix ]; then "
         "cp -p b9_seeded_fuzzing.py b9_seeded_fuzzing.py.bak_quantile_fix && "
         "echo BACKUP_CREATED; else echo BACKUP_ALREADY_PRESENT; fi; "
         "md5sum b9_seeded_fuzzing.py b9_seeded_fuzzing.py.bak_quantile_fix", timeout=60)

sftp = c.open_sftp()
src_md5 = put(sftp, "src/experiments/external_ports/b9_seeded_fuzzing.py", REMOTE_SRC)
test_md5 = put(sftp, "tests/test_b9_error_stats_bitexact.py", REMOTE_TEST)
sftp.close()
print("local md5: src=%s test=%s" % (src_md5, test_md5))

print("### verify upload + import")
R.run(c, "md5sum %s %s; cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= %s -c "
         "\"from src.experiments.external_ports import b9_seeded_fuzzing as b; "
         "print('QUANTILE_NUMEL_LIMIT', b.QUANTILE_NUMEL_LIMIT, b.QUANTILE_NUMEL_LIMIT == 2**24)\""
      % (REMOTE_SRC, REMOTE_TEST, PY), timeout=180)

print("### new bit-exactness suite")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=24 MKL_NUM_THREADS=24 "
         "%s -m pytest tests/test_b9_error_stats_bitexact.py -q 2>&1 | tail -25" % PY,
      timeout=3600)

print("### regression: existing E3 port suite")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=24 MKL_NUM_THREADS=24 "
         "%s -m pytest tests/test_e3_ports.py -q 2>&1 | tail -20" % PY,
      timeout=3600)

c.close()
print("DEPLOY_DONE")
