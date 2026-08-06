"""Inspect the failing candidate + parse-check ALL staged wave-1 candidates."""
import _remote as R

py = r"""
import ast, json
from pathlib import Path

f = Path('/root/mk_v2_runs/e3_corpora/c3_wave1/candidates/'
         '018d33522a22175ec60cf51016b304ec685f6b1742e120f635be15eea822be7f.py')
text = f.read_text(encoding='utf-8')
lines = text.splitlines()
print('total lines:', len(lines))
for i in range(20, 30):
    print('%3d| %s' % (i + 1, lines[i][:100]))
try:
    ast.parse(text)
    print('ast.parse: OK ?!')
except SyntaxError as exc:
    print('ast.parse FAILS:', exc)

# parse-check everything staged
bad = []
for corpus in ('c3_wave1', 'c5_wave1'):
    for p in Path(f'/root/mk_v2_runs/e3_corpora/{corpus}/candidates').glob('*.py'):
        try:
            ast.parse(p.read_text(encoding='utf-8'))
        except SyntaxError as exc:
            bad.append((corpus, p.name[:16], 'line %s' % exc.lineno))
print('unparseable candidates:', len(bad))
for b in bad[:10]:
    print('  ', b)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_syntax_check.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_syntax_check.py",
      timeout=600)
c.close()
print("SYNTAX_CHECK_DONE")
