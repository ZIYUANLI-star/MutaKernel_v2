"""Diagnose why the unmutated L1_P17 control produced zero rounds in 900s."""
import _wcx

PY = "/root/miniconda3/bin/python"

CMDS = [
    ("ext_cache",
     "ls -la --time-style=+%F_%T /root/mk_v2_runs/torch_ext 2>/dev/null | "
     "grep -i -E 'p17|17' ; echo '---ALL(count)'; "
     "ls /root/mk_v2_runs/torch_ext 2>/dev/null | wc -l; echo '---NEWEST'; "
     "ls -lt --time-style=+%F_%T /root/mk_v2_runs/torch_ext 2>/dev/null | head -12"),
    ("worker_naming",
     "grep -n -E 'load_inline|name=|extra_cflags|build_directory|_seed_all' "
     "/root/mk_v2/scripts/_mutant_worker.py | head -40"),
    ("p17_source",
     "%s - <<'PYEOF'\n"
     "import json,glob,re\n"
     "for f in glob.glob('/root/mk_v2_runs/e1/*probe*.json'):\n"
     "    pass\n"
     "import sys; sys.path.insert(0,'/root/mk_v2')\n"
     "import scripts.run_e1_probe_study as ps\n"
     "from pathlib import Path\n"
     "kfs=ps._load_probe_files(Path('/root/mk_v2_runs/e1'))\n"
     "for kf in kfs:\n"
     "    k=kf['kernel']\n"
     "    if 'L%%s_P%%s'%%(k['level'],k['problem_id'])!='L1_P17': continue\n"
     "    src=kf['kernel_source']\n"
     "    print('SOURCE_LEN',len(src))\n"
     "    for i,l in enumerate(src.splitlines(),1):\n"
     "        if '__syncthreads' in l or '__global__' in l or 'while' in l or 'for (' in l:\n"
     "            print('%%4d| %%s'%%(i,l))\n"
     "    print('---FULL---'); print(src[:4000])\n"
     "PYEOF" % PY),
]


def main():
    with _wcx.Session(label="p17 ") as s:
        for name, cmd in CMDS:
            print("\n##### %s #####" % name.upper(), flush=True)
            print(s.out(cmd, timeout=240, default="FAILED:").rstrip(), flush=True)
    print("\nP17_DONE")


if __name__ == "__main__":
    main()
