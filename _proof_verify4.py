"""Substantive spot-check v2: load per-kernel probe files, verify premise."""
import _remote as R

verify_py = r"""
import ast, json

PROVEN = {
    "L1_P1": ["L1_P1__const_perturb__0", "L1_P1__const_perturb__1"],
    "L1_P14": ["L1_P14__const_perturb__0", "L1_P14__const_perturb__1"],
    "L1_P21": ["L1_P21__const_perturb__19"],
    "L1_P6": ["L1_P6__const_perturb__4", "L1_P6__const_perturb__5",
              "L1_P6__const_perturb__2"],
    "L2_P64": ["L2_P64__const_perturb__25"],
}

def check(code, line):
    tree = ast.parse(code)
    var = None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign) and node.lineno == line:
            for t in node.targets:
                if isinstance(t, ast.Name):
                    var = t.id
    if var is None:
        return None, [], 'NO_MODULE_LEVEL_ASSIGN_AT_SITE'
    refs = []
    stack = ['<module>']
    class V(ast.NodeVisitor):
        def visit_ClassDef(self, n):
            stack.append('class ' + n.name); self.generic_visit(n); stack.pop()
        def visit_FunctionDef(self, n):
            stack.append('def ' + n.name); self.generic_visit(n); stack.pop()
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_Name(self, n):
            if n.id == var:
                refs.append((n.lineno, ' / '.join(stack)))
            self.generic_visit(n)
    V().visit(tree)
    bad = [(ln, s) for ln, s in refs if ln != line
           and 'get_inputs' not in s and 'get_init_inputs' not in s]
    return var, refs, ('SOUND' if not bad else 'NEEDS_REVIEW %r' % bad)

for kern, pids in PROVEN.items():
    data = json.load(open('/root/mk_v2_runs/e1/probes/%s.json' % kern))
    plist = data if isinstance(data, list) else \
        data.get('probes') or data.get('mutants') or []
    by_id = {}
    for p in plist:
        if isinstance(p, dict):
            by_id[p.get('probe_id') or p.get('id')] = p
    for pid in pids:
        p = by_id.get(pid)
        print('=' * 70)
        if p is None:
            print(pid, 'NOT FOUND; file keys:',
                  list(data.keys())[:8] if isinstance(data, dict) else len(plist))
            continue
        code = p.get('mutated_code') or p.get('mutated_source') or ''
        site = p.get('site') or {}
        line = site.get('line_start') or p.get('line_start')
        if not code or not line:
            print(pid, 'missing code/line; keys:', sorted(p.keys()))
            continue
        var, refs, verdict = check(code, line)
        stmt = code.splitlines()[line-1].strip()[:70]
        print('%s\n  site line %s: %s\n  var=%s' % (pid, line, stmt, var))
        for ln, s in refs:
            print('   ref line %4d in %s' % (ln, s))
        print('  VERDICT:', verdict)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_proof_verify4.py", "w") as fh:
    fh.write(verify_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _proof_verify4.py",
      timeout=300)
c.close()
print("PROOF_VERIFY4_DONE")
