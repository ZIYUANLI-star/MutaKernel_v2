"""Run the canonical _wc_analyze.py on the remote host and capture its output."""
import pathlib

import _wcx

PY = "/root/miniconda3/bin/python"


def main():
    with _wcx.Session(label="analyze ") as s:
        print("##### MD5 (canonical check) #####")
        print(s.out("md5sum /root/mk_v2/_wc_analyze.py", timeout=60).rstrip())
        print("\n##### RUN #####")
        code, out, err = s.run("cd /root/mk_v2 && %s _wc_analyze.py 2>&1" % PY,
                               timeout=300)
        pathlib.Path("_wc_remote/wc1_analyze_stdout.txt").write_text(
            out, encoding="utf-8")
        print("exit=%d, %d bytes captured -> _wc_remote/wc1_analyze_stdout.txt"
              % (code, len(out)))
        print(out[:3000])
    print("\nANALYZE_DONE")


if __name__ == "__main__":
    main()
