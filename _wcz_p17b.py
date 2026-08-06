"""Is the L1_P17 control blocked by an incomplete / locked extension build?"""
import _wcx

EXT = "/root/mk_v2_runs/torch_ext"
BAD = EXT + "/matmul_cuda_eqm_L1_P17__WC_AUDIT_CONTROL__equiv"

CMDS = [
    ("bad_dir", "ls -la --time-style=+%F_%T " + BAD),
    ("healthy_dir",
     "ls -la --time-style=+%%F_%%T %s/matmul_cuda_eqm_L1_P17__sync_remove__1" % EXT),
    ("other_controls",
     "for d in %s/*WC_AUDIT_CONTROL*; do printf '%%-70s ' \"$(basename $d)\"; "
     "ls $d | tr '\\n' ' '; echo; done" % EXT),
    ("locks", "find %s -maxdepth 2 -name 'lock' -o -maxdepth 2 -name '*.baton' "
              "2>/dev/null | head -20" % EXT),
]


def main():
    with _wcx.Session(label="p17b ") as s:
        for name, cmd in CMDS:
            print("\n##### %s #####" % name.upper(), flush=True)
            print(s.out(cmd, timeout=180, default="FAILED:").rstrip(), flush=True)
    print("\nP17B_DONE")


if __name__ == "__main__":
    main()
