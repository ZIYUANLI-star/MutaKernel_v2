"""Pull the whole cells/ directory as a tarball for offline analysis."""
import base64
import io
import pathlib
import tarfile

import _wcx

WC = "/root/mk_v2_runs/e1/witness_confirmation"
LOCAL = pathlib.Path("_wc_remote/cells")


def main():
    LOCAL.mkdir(parents=True, exist_ok=True)
    with _wcx.Session(label="pull ") as s:
        s.run("cd %s && tar czf /tmp/_wc_cells.tgz cells" % WC, timeout=300)
        size = s.out("stat -c %s /tmp/_wc_cells.tgz", timeout=60).strip()
        print("remote tarball bytes:", size)
        b64 = s.out("base64 -w0 /tmp/_wc_cells.tgz", timeout=600)
    raw = base64.b64decode(b64.strip())
    print("fetched bytes:", len(raw))
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        members = [m for m in tf.getmembers() if m.isfile()]
        for m in members:
            m.name = pathlib.PurePosixPath(m.name).name
            tf.extract(m, LOCAL)
    print("extracted %d cell files to %s" % (len(members), LOCAL))


if __name__ == "__main__":
    main()
