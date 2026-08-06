"""Upload + unpack the C5 wave-1 package; verify count and a sample hash."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put(r"_e3_stage\c5_wave1.tar.gz", "/root/mk_v2/external/c5_wave1.tar.gz")
sftp.close()
_, o, e = _remote.run(c, (
    "cd /root/mk_v2/external && tar xzf c5_wave1.tar.gz && "
    "mv -T c5_wave1 C5_kernelbench_samples_wave1 2>/dev/null || true; "
    "ls /root/mk_v2/external/C5_kernelbench_samples_wave1 | wc -l; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, hashlib, glob\n"
    "reg=json.load(open('/root/mk_v2/external/C5_kernelbench_samples_wave1/registry.json'))\n"
    "subs=reg['subjects']\n"
    "print('registry subjects:', len(subs))\n"
    "bad=0\n"
    "for s in subs:\n"
    "    p='/root/mk_v2/external/C5_kernelbench_samples_wave1/%s/kernel.json' % s['stable_id'][:16]\n"
    "    d=json.load(open(p))\n"
    "    h=hashlib.sha256(d['kernel'].encode()).hexdigest()\n"
    "    if h!=s['raw_sha256']: bad+=1\n"
    "print('hash-verified all, mismatches:', bad)\n"
    "EOF"),
    timeout=300, echo=False)
print(o)
if e.strip():
    print("STDERR:\n" + e[-1500:])
c.close()
